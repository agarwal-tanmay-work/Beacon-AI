"""Gemini REST client with a real fallback chain.

What changed compared with the old ``GeminiService`` (and why):

* **Model fallback.** The old code defined model lists but only ever used one hard-coded model, so the
  day Google restricted ``gemini-2.5-flash`` every chat turn failed. ``generate`` now walks an ordered
  chain, skipping models whose circuit breaker is open, and classifies every failure (see ``errors.py``).
* **API key in a header**, never in the URL: httpx logs request URLs, which is how keys ended up in
  logs and in git history.
* **No ``temperature`` / ``topP`` / ``topK``.** Gemini 3.6+ ignores them and will start returning HTTP 400
  for them; earlier Gemini 3 models degrade when they are changed from their defaults.
* **Thinking is capped** (``thinkingLevel: low``) and ``maxOutputTokens`` is generous, because thinking
  tokens count against ``maxOutputTokens`` and an exhausted budget returns an *empty* response - the
  most common cause of "random" chat failures with thinking models.
* **Tolerant parsing**: multiple parts, thought parts, missing ``parts`` and safety blocks are handled
  explicitly instead of raising ``KeyError``.
* Everything runs on the application's event loop (the old evidence code created a second loop in a
  worker thread and shared one HTTP client between them).
"""

import asyncio
import json
import random
import re
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Any, TypeVar

import httpx
import structlog

from app.core.config import settings
from app.services.gemini.errors import (
    Attempt,
    GeminiAuthError,
    GeminiBadRequest,
    GeminiBlocked,
    GeminiEmptyResponse,
    GeminiError,
    GeminiMalformedResponse,
    GeminiModelUnavailable,
    GeminiNetworkError,
    GeminiNotConfigured,
    GeminiOverloaded,
    GeminiQuotaExceeded,
    GeminiRateLimited,
    GeminiTimeout,
    GeminiUnavailable,
)
from app.services.gemini.registry import FAST_CHAIN, QUALITY_CHAIN, ModelRegistry

logger = structlog.get_logger(__name__)
T = TypeVar("T")

_BLOCKING_FINISH_REASONS = frozenset(
    {
        "SAFETY",
        "PROHIBITED_CONTENT",
        "BLOCKLIST",
        "SPII",
        "RECITATION",
        "LANGUAGE",
        "IMAGE_SAFETY",
        "IMAGE_PROHIBITED_CONTENT",
        "IMAGE_RECITATION",
    }
)
_THINKING_BUDGETS = {"minimal": 0, "low": 0, "medium": 1024, "high": 4096}  # only used by the legacy 2.5 family
_MIN_ATTEMPT_SECONDS = 2.0  # do not start a new attempt with less budget than this
_KEY_PAUSE_SECONDS = 60.0  # after an auth error, fail fast for this long instead of hammering the API
_MAX_TOKEN_CEILING = 16384  # upper bound when retrying a truncated answer with a bigger budget
_DISCOVERY_RETRY_SECONDS = 300.0


# ======================================================================================
# Request / result types
# ======================================================================================
@dataclass
class GenerationRequest:
    contents: list[dict[str, Any]]
    system_instruction: str | None = None
    response_schema: dict[str, Any] | None = None  # sanitised JSON schema -> JSON output
    max_output_tokens: int = 4096
    thinking: str | None = "low"  # "minimal" | "low" | "medium" | "high" | None (= leave the model default)
    timeout: float = 25.0  # seconds per attempt
    deadline: float = 45.0  # seconds for the whole chain
    profile: str = "quality"  # "quality" | "fast"
    label: str = "generic"  # task name, for logs only


@dataclass
class GenerationResult:
    text: str
    model: str
    finish_reason: str | None
    latency_ms: int
    prompt_tokens: int | None = None
    output_tokens: int | None = None
    thought_tokens: int | None = None
    attempts: list[Attempt] = field(default_factory=list)


# ======================================================================================
# Pure helpers (unit-tested directly)
# ======================================================================================
def _short(text: str, limit: int = 200) -> str:
    return " ".join(text.split())[:limit]


def _retry_after_seconds(error: Mapping[str, Any], headers: Mapping[str, str] | None) -> float | None:
    if headers:
        value = headers.get("retry-after") or headers.get("Retry-After")
        if value and value.strip().isdigit():
            return float(value)
    for detail in error.get("details") or []:
        if isinstance(detail, dict):
            delay = detail.get("retryDelay")
            if isinstance(delay, str):
                match = re.fullmatch(r"\s*([\d.]+)s\s*", delay)
                if match:
                    return float(match.group(1))
    match = re.search(r"retry in ([\d.]+)\s*s", str(error.get("message") or ""), re.IGNORECASE)
    return float(match.group(1)) if match else None


def _quota_scope(error: Mapping[str, Any]) -> str:
    """'daily' when the 429 is about a per-day / zero quota, else 'minute' (or 'unknown')."""
    text = str(error.get("message") or "").lower()
    quota_ids: list[str] = []
    for detail in error.get("details") or []:
        if isinstance(detail, dict):
            for violation in detail.get("violations") or []:
                if isinstance(violation, dict):
                    quota_ids.append(f"{violation.get('quotaId', '')} {violation.get('quotaMetric', '')}".lower())
    blob = " ".join(quota_ids) + " " + text
    if "perday" in blob or "per day" in blob or "daily" in blob or "limit: 0" in blob:
        return "daily"
    if "perminute" in blob or "per minute" in blob:
        return "minute"
    return "unknown"


def classify_http_error(status: int, body: Any, headers: Mapping[str, str] | None = None) -> GeminiError:
    """Map an HTTP error response to the exception class that tells the chain what to do next."""
    error: Mapping[str, Any] = body.get("error", {}) if isinstance(body, dict) and isinstance(body.get("error"), dict) else {}
    message = str(error.get("message") or "")
    api_status = str(error.get("status") or "").upper()  # RESOURCE_EXHAUSTED, NOT_FOUND ...
    string_code = error["code"] if isinstance(error.get("code"), str) else ""  # newer API style: "model_not_found"
    text = f"{message} {api_status} {string_code}".lower()
    retry_after = _retry_after_seconds(error, headers)
    brief = _short(message)

    # --- credentials / project level: no other model can help ---------------------------
    if status == 401 or any(
        marker in text
        for marker in (
            "api key not valid",
            "api_key_invalid",
            "api key expired",
            "reported as leaked",
            "invalid api key",
            "api key is invalid",
            "service_disabled",
            "has not been used in project",
            "api has not been enabled",
        )
    ):
        return GeminiAuthError(brief or "invalid API key", status_code=status)
    if "location is not supported" in text or status == 402 or (status in (400, 403) and "billing" in text and "enable" in text):
        return GeminiAuthError(brief or "project cannot use the API", status_code=status)

    # --- model level --------------------------------------------------------------------
    if status == 404 or api_status == "NOT_FOUND" or string_code == "model_not_found":
        return GeminiModelUnavailable(brief or "model not found", status_code=status)
    if status == 403 or api_status == "PERMISSION_DENIED" or string_code == "permission_denied":
        return GeminiModelUnavailable(brief or "model not permitted for this project", status_code=status)

    # --- quota / rate limits ------------------------------------------------------------
    if status == 429 or api_status == "RESOURCE_EXHAUSTED" or string_code in ("rate_limit_exceeded", "quota_exceeded", "too_many_requests"):
        scope = _quota_scope(error)
        if scope == "daily" or string_code == "quota_exceeded" or (scope == "unknown" and (retry_after or 0) > 90):
            return GeminiQuotaExceeded(brief or "quota exceeded", status_code=status, retry_after=retry_after)
        return GeminiRateLimited(brief or "rate limited", status_code=status, retry_after=retry_after)

    # --- transient server side ----------------------------------------------------------
    if status in (408, 499, 504):
        return GeminiTimeout(brief or "upstream timeout", status_code=status)
    if status >= 500:
        return GeminiOverloaded(brief or "upstream error", status_code=status, retry_after=retry_after)

    # --- our request was wrong ----------------------------------------------------------
    if status == 400 or api_status in ("INVALID_ARGUMENT", "FAILED_PRECONDITION"):
        if re.search(r"thinking|thought", text):
            return GeminiBadRequest(brief, status_code=status, adaptation="thinking")
        if re.search(r"response_?(json_?)?schema|response_?format|response_?mime|json schema|unknown name", text):
            return GeminiBadRequest(brief, status_code=status, adaptation="schema")
        if "safety" in text or "blocked" in text:
            return GeminiBlocked("safety", status_code=status)
        return GeminiBadRequest(brief, status_code=status)
    return GeminiBadRequest(brief or f"HTTP {status}", status_code=status)


def extract_text(data: Any) -> tuple[str, str | None, dict[str, Any]]:
    """Pull the answer out of a 200 response. Raises for blocks and for answers with no text."""
    if not isinstance(data, dict):
        raise GeminiMalformedResponse("response body was not a JSON object")
    feedback = data.get("promptFeedback") or {}
    if isinstance(feedback, dict) and feedback.get("blockReason"):
        raise GeminiBlocked(str(feedback["blockReason"]))
    candidates = data.get("candidates") or []
    if not candidates or not isinstance(candidates[0], dict):
        raise GeminiEmptyResponse("no candidates returned")
    candidate = candidates[0]
    finish = candidate.get("finishReason")
    parts = (candidate.get("content") or {}).get("parts") or []
    text = "".join(
        part["text"] for part in parts if isinstance(part, dict) and isinstance(part.get("text"), str) and not part.get("thought")
    )
    usage = data.get("usageMetadata") if isinstance(data.get("usageMetadata"), dict) else {}
    if finish in _BLOCKING_FINISH_REASONS:
        raise GeminiBlocked(str(finish))
    if not text.strip():
        # MAX_TOKENS with no text = the whole budget went into thinking.
        empty = GeminiEmptyResponse(f"no text (finishReason={finish})")
        empty.truncated = finish == "MAX_TOKENS"
        raise empty
    return text, finish, usage


def build_payload(
    request: GenerationRequest, model: str, registry: ModelRegistry, *, max_output_tokens: int | None = None
) -> dict[str, Any]:
    caps = registry.caps(model)
    generation_config: dict[str, Any] = {"maxOutputTokens": max_output_tokens or request.max_output_tokens}

    level = request.thinking
    if level:
        if caps.thinking_style == "level_upper":
            generation_config["thinkingConfig"] = {"thinkingLevel": level.upper()}
        elif caps.thinking_style == "level_lower":
            generation_config["thinkingConfig"] = {"thinkingLevel": level.lower()}
        elif caps.thinking_style == "budget":
            generation_config["thinkingConfig"] = {"thinkingBudget": _THINKING_BUDGETS.get(level, 0)}

    system = request.system_instruction
    schema = request.response_schema
    if schema:
        if caps.schema_style == "json_schema":
            generation_config["responseMimeType"] = "application/json"
            generation_config["responseJsonSchema"] = schema
        elif caps.schema_style == "response_format":
            generation_config["responseFormat"] = {"text": {"mimeType": "APPLICATION_JSON", "schema": schema}}
        else:  # prompt-only: still ask for JSON mode, describe the shape in words
            generation_config["responseMimeType"] = "application/json"
            system = (
                (system + "\n\n" if system else "")
                + "Respond with ONLY a JSON value that satisfies this JSON Schema:\n"
                + json.dumps(schema)
            )

    payload: dict[str, Any] = {"contents": request.contents, "generationConfig": generation_config}
    if system:
        payload["systemInstruction"] = {"parts": [{"text": system}]}
    return payload


# ======================================================================================
# Client
# ======================================================================================
class GeminiClient:
    def __init__(
        self,
        *,
        registry: ModelRegistry | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
        sleep: Callable[[float], Any] | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.registry = registry or ModelRegistry(
            quality=tuple(settings.GEMINI_MODELS) or QUALITY_CHAIN,
            fast=tuple(settings.GEMINI_FAST_MODELS) or FAST_CHAIN,
            clock=clock,
        )
        self._transport = transport
        self._sleep = sleep or asyncio.sleep
        self._clock = clock
        self._http: httpx.AsyncClient | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._semaphore: asyncio.Semaphore | None = None
        self._key_paused_until = 0.0
        self._key_error: str | None = None
        self._last_success_at: float | None = None
        self._discovery_task: asyncio.Task[Any] | None = None
        self._last_discovery_attempt = float("-inf")

    # ---- plumbing -----------------------------------------------------------------
    def _client(self) -> httpx.AsyncClient:
        loop = asyncio.get_running_loop()
        if self._http is None or self._http.is_closed or self._loop is not loop:
            self._http = httpx.AsyncClient(
                transport=self._transport,
                limits=httpx.Limits(max_connections=20, max_keepalive_connections=10),
            )
            self._loop = loop
            self._semaphore = asyncio.Semaphore(settings.GEMINI_MAX_CONCURRENCY)
        return self._http

    async def aclose(self) -> None:
        if self._discovery_task and not self._discovery_task.done():
            self._discovery_task.cancel()
        if self._http is not None and not self._http.is_closed:
            await self._http.aclose()
        self._http = None

    @staticmethod
    def _headers(api_key: str) -> dict[str, str]:
        return {"x-goog-api-key": api_key, "Content-Type": "application/json"}

    @property
    def configured(self) -> bool:
        return bool(settings.gemini_api_key)

    # ---- discovery ----------------------------------------------------------------
    async def discover_models(self) -> bool:
        """Ask the API which models exist. Best effort: the static chain keeps working if this fails."""
        api_key = settings.gemini_api_key
        if not api_key or not settings.GEMINI_AUTO_DISCOVER:
            return False
        http = self._client()
        models: list[dict[str, Any]] = []
        page_token: str | None = None
        try:
            for _ in range(5):
                params: dict[str, Any] = {"pageSize": 1000}
                if page_token:
                    params["pageToken"] = page_token
                response = await http.get(
                    f"{settings.GEMINI_API_BASE_URL}/models", params=params, headers=self._headers(api_key), timeout=10.0
                )
                if response.status_code != 200:
                    error = classify_http_error(response.status_code, _safe_json(response), response.headers)
                    if isinstance(error, GeminiAuthError):
                        self._pause_key(error)
                    logger.warning("gemini_discovery_failed", status=response.status_code, kind=error.kind)
                    return False
                body = response.json()
                models.extend(body.get("models") or [])
                page_token = body.get("nextPageToken")
                if not page_token:
                    break
        except (httpx.HTTPError, ValueError) as exc:
            logger.warning("gemini_discovery_failed", error_type=type(exc).__name__)
            return False
        self.registry.apply_discovery(models)
        logger.info("gemini_discovery_ok", models=len(models), chain=self.registry.chain("quality")[:6])
        return True

    def schedule_discovery_if_stale(self) -> None:
        """Fire-and-forget refresh (called opportunistically from request paths and the sweeper)."""
        if not self.configured or not settings.GEMINI_AUTO_DISCOVER or not self.registry.needs_discovery():
            return
        if self._discovery_task and not self._discovery_task.done():
            return
        if self._clock() - self._last_discovery_attempt < _DISCOVERY_RETRY_SECONDS:
            return  # do not hammer ListModels while it keeps failing
        self._last_discovery_attempt = self._clock()
        self._discovery_task = asyncio.create_task(self.discover_models())

    # ---- key state ----------------------------------------------------------------
    def _pause_key(self, error: GeminiError) -> None:
        self._key_paused_until = self._clock() + _KEY_PAUSE_SECONDS
        self._key_error = error.summary + ": " + _short(str(error), 120)
        logger.error("gemini_api_key_rejected", detail=self._key_error)

    # ---- the fallback loop -------------------------------------------------------
    async def generate(
        self,
        request: GenerationRequest,
        parser: Callable[[str], T] | None = None,
    ) -> tuple[T | str, GenerationResult]:
        """Run ``request`` against the model chain; return ``(parsed_or_text, result)``.

        ``parser`` runs *inside* the loop, so an answer that does not parse counts as a failed attempt and
        the next model gets a go - a flaky model can no longer take a chat turn down with it.
        Raises ``GeminiNotConfigured``, ``GeminiAuthError``, ``GeminiBlocked`` or ``GeminiUnavailable``.
        """
        api_key = settings.gemini_api_key
        if not api_key:
            raise GeminiNotConfigured("GEMINI_API_KEY is not set")
        now = self._clock()
        if now < self._key_paused_until:
            raise GeminiAuthError(self._key_error or "API key rejected")

        http = self._client()
        self.schedule_discovery_if_stale()
        started = self._clock()
        deadline = started + request.deadline
        attempts: list[Attempt] = []
        blocked: GeminiBlocked | None = None

        assert self._semaphore is not None
        try:
            await asyncio.wait_for(self._semaphore.acquire(), timeout=max(0.1, request.deadline))
        except TimeoutError as exc:
            raise GeminiUnavailable(attempts, retry_after=5.0) from exc
        try:
            candidates = self.registry.candidates(request.profile)
            forced = not candidates
            if forced:  # everything is paused - only probe if a pause is about to end
                candidates = self.registry.force_candidate(request.profile)
            for model in candidates:
                if deadline - self._clock() < _MIN_ATTEMPT_SECONDS:
                    break
                if not self.registry.begin_attempt(model, force=forced):
                    continue  # someone else is already probing this paused model
                try:
                    outcome = await self._try_model(http, api_key, model, request, parser, deadline, attempts)
                except GeminiAuthError as exc:
                    self._pause_key(exc)
                    raise
                except GeminiBlocked as exc:
                    blocked = exc
                    if sum(1 for a in attempts if a.outcome == "blocked") >= 2:
                        break  # two independent models refused the content - stop shopping around
                    continue
                finally:
                    self.registry.release(model)  # never leave a probe slot claimed (errors, cancellation, ...)
                if outcome is not None:
                    value, result = outcome
                    self._last_success_at = self._clock()
                    result.attempts = attempts
                    return value, result
        finally:
            self._semaphore.release()

        if blocked is not None and all(a.outcome in ("blocked", "bad_request") for a in attempts):
            raise GeminiBlocked(blocked.reason)
        raise GeminiUnavailable(attempts, retry_after=self.registry.earliest_retry(request.profile) or None, blocked=blocked is not None)

    async def _try_model(
        self,
        http: httpx.AsyncClient,
        api_key: str,
        model: str,
        request: GenerationRequest,
        parser: Callable[[str], T] | None,
        deadline: float,
        attempts: list[Attempt],
    ) -> tuple[T | str, GenerationResult] | None:
        """Up to two tries on one model (plus request adaptations). ``None`` = move on to the next model."""
        tries = 0
        adaptations = 0
        max_tokens = request.max_output_tokens
        while tries < 2:
            remaining = deadline - self._clock()
            if remaining < _MIN_ATTEMPT_SECONDS:
                return None
            t0 = self._clock()
            try:
                payload = build_payload(request, model, self.registry, max_output_tokens=max_tokens)
                text, finish, usage = await self._post(http, api_key, model, payload, min(request.timeout, remaining))
                try:
                    value: T | str = parser(text) if parser else text
                except GeminiMalformedResponse as parse_error:
                    parse_error.truncated = finish == "MAX_TOKENS"
                    raise
            except GeminiBadRequest as exc:
                self._log_attempt(request, model, exc, t0)
                attempts.append(Attempt(model, exc.kind, exc.status_code, self._ms(t0), str(exc)[:160]))
                if adaptations < 3 and self._adapt(model, exc):
                    adaptations += 1
                    continue  # same model, adjusted request - does not use up a try
                self.registry.record_failure(model, exc)
                return None
            except GeminiBlocked as exc:
                self._log_attempt(request, model, exc, t0)
                attempts.append(Attempt(model, exc.kind, exc.status_code, self._ms(t0), exc.reason))
                self.registry.record_failure(model, exc)
                raise
            except GeminiAuthError as exc:
                attempts.append(Attempt(model, exc.kind, exc.status_code, self._ms(t0), str(exc)[:160]))
                raise
            except (GeminiOverloaded, GeminiNetworkError, GeminiEmptyResponse, GeminiMalformedResponse) as exc:
                self._log_attempt(request, model, exc, t0)
                attempts.append(Attempt(model, exc.kind, exc.status_code, self._ms(t0), str(exc)[:160]))
                tries += 1
                if exc.truncated:  # thinking + answer overflowed maxOutputTokens: give the retry more room
                    max_tokens = min(max_tokens * 2, _MAX_TOKEN_CEILING)
                if tries < 2 and deadline - self._clock() > _MIN_ATTEMPT_SECONDS + 1.0:
                    await self._sleep(random.uniform(0.3, 0.8))
                    continue
                self.registry.record_failure(model, exc)
                return None
            except GeminiError as exc:  # timeout, rate limit, quota, model unavailable: no point retrying this model now
                self._log_attempt(request, model, exc, t0)
                attempts.append(Attempt(model, exc.kind, exc.status_code, self._ms(t0), str(exc)[:160]))
                self.registry.record_failure(model, exc)
                return None

            latency = self._ms(t0)
            attempts.append(Attempt(model, "ok", 200, latency))
            self.registry.record_success(model)
            logger.info(
                "gemini_attempt",
                task=request.label,
                model=model,
                outcome="ok",
                latency_ms=latency,
                finish=finish,
                prompt_tokens=usage.get("promptTokenCount"),
                output_tokens=usage.get("candidatesTokenCount"),
                thought_tokens=usage.get("thoughtsTokenCount"),
                fallback_depth=sum(1 for a in attempts if a.outcome != "ok"),
            )
            return value, GenerationResult(
                text=text,
                model=model,
                finish_reason=finish,
                latency_ms=latency,
                prompt_tokens=usage.get("promptTokenCount"),
                output_tokens=usage.get("candidatesTokenCount"),
                thought_tokens=usage.get("thoughtsTokenCount"),
            )
        return None

    def _adapt(self, model: str, error: GeminiBadRequest) -> bool:
        """Make the request for ``model`` less demanding after a 400. Returns False when nothing is left to relax."""
        caps = self.registry.caps(model)
        if error.adaptation == "schema":
            changed = caps.degrade_schema()
        elif error.adaptation == "thinking":
            changed = caps.degrade_thinking()
        else:
            return False
        if changed:
            logger.warning(
                "gemini_request_adapted", model=model, adaptation=error.adaptation, thinking=caps.thinking_style, schema=caps.schema_style
            )
        return changed

    async def _post(
        self, http: httpx.AsyncClient, api_key: str, model: str, payload: dict[str, Any], timeout: float
    ) -> tuple[str, str | None, dict[str, Any]]:
        url = f"{settings.GEMINI_API_BASE_URL}/models/{model}:generateContent"
        try:
            response = await http.post(
                url,
                json=payload,
                headers=self._headers(api_key),
                timeout=httpx.Timeout(timeout, connect=min(5.0, timeout)),
            )
        except httpx.TimeoutException as exc:
            raise GeminiTimeout(f"{type(exc).__name__} after {timeout:.0f}s") from exc
        except httpx.TransportError as exc:  # connect / DNS / TLS / protocol errors
            raise GeminiNetworkError(type(exc).__name__) from exc

        if response.status_code != 200:
            raise classify_http_error(response.status_code, _safe_json(response), response.headers)
        try:
            data = response.json()
        except ValueError as exc:
            raise GeminiMalformedResponse("response body was not JSON") from exc
        return extract_text(data)

    # ---- small utilities ------------------------------------------------------------
    def _ms(self, t0: float) -> int:
        return int((self._clock() - t0) * 1000)

    def _log_attempt(self, request: GenerationRequest, model: str, error: GeminiError, t0: float) -> None:
        logger.warning(
            "gemini_attempt",
            task=request.label,
            model=model,
            outcome=error.kind,
            status=error.status_code,
            latency_ms=self._ms(t0),
            retry_after=error.retry_after,
            detail=_short(str(error), 160),
        )

    # ---- health ---------------------------------------------------------------------
    def health(self) -> str:
        """Coarse state for /health: unconfigured | key_invalid | ok | degraded | unknown."""
        if not self.configured:
            return "unconfigured"
        if self._clock() < self._key_paused_until:
            return "key_invalid"
        if not self.registry.candidates("quality"):
            return "degraded"
        return "ok" if self._last_success_at is not None else "unknown"

    def status(self) -> dict[str, Any]:
        return {
            "state": self.health(),
            "configured": self.configured,
            "key_error": self._key_error if self._clock() < self._key_paused_until else None,
            "seconds_since_last_success": None if self._last_success_at is None else round(self._clock() - self._last_success_at),
            "quality_chain": self.registry.snapshot("quality"),
            "fast_chain": self.registry.snapshot("fast"),
        }


def _safe_json(response: httpx.Response) -> Any:
    try:
        return response.json()
    except ValueError:
        return None


# One shared client for the application. Tests construct their own with a mock transport.
gemini = GeminiClient()
