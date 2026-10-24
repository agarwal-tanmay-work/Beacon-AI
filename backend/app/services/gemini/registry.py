"""Which Gemini models to try, in which order, and which ones are currently healthy.

Model names are the part of this system that rots fastest (Google retires or restricts models every
few months), so nothing here is a single point of failure:

* the preference chains below are just defaults - override with ``GEMINI_MODELS`` / ``GEMINI_FAST_MODELS``;
* when ``GEMINI_AUTO_DISCOVER`` is on, the API's own model list is used to demote models that do not
  exist and to pick up newer Flash models that this file has never heard of;
* every model has a circuit breaker, so a retired / quota-exhausted / overloaded model is skipped
  for a while instead of costing every request a failed round trip.
"""

import re
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from app.services.gemini.errors import GeminiError

# Order = preference. Verified against https://ai.google.dev/gemini-api/docs/models (2026-10-22).
QUALITY_CHAIN: tuple[str, ...] = (
    "gemini-3.8-flash",
    "gemini-3.6-flash",
    "gemini-3.5-flash-lite",
    "gemini-3.1-flash-lite",
    "gemini-flash-latest",
    "gemini-flash-lite-latest",
    # Not deprecated, but Google now only serves them to projects that already used them.
    # Last resort; the breaker removes them for hours after the first 404/403.
    "gemini-2.5-flash",
    "gemini-2.5-flash-lite",
)
FAST_CHAIN: tuple[str, ...] = (
    "gemini-3.5-flash-lite",
    "gemini-3.8-flash",
    "gemini-3.6-flash",
    "gemini-3.1-flash-lite",
    "gemini-flash-lite-latest",
    "gemini-flash-latest",
    "gemini-2.5-flash-lite",
    "gemini-2.5-flash",
)

_GA_FLASH = re.compile(r"^gemini-(\d+)(?:\.(\d+))?-flash(-lite)?$")
_VERSION = re.compile(r"^gemini-(\d+)(?:\.(\d+))?-")


@dataclass
class ModelCaps:
    """How to ask this particular model for 'low thinking' and for JSON. Degrades when the API objects."""

    thinking_style: str = "level_upper"  # level_upper -> level_lower -> none   (2.5 family: budget -> none)
    schema_style: str = "json_schema"  # json_schema -> response_format -> prompt

    def degrade_thinking(self) -> bool:
        order = {"level_upper": "level_lower", "level_lower": "none", "budget": "none"}
        nxt = order.get(self.thinking_style)
        if nxt is None:
            return False
        self.thinking_style = nxt
        return True

    def degrade_schema(self) -> bool:
        order = {"json_schema": "response_format", "response_format": "prompt"}
        nxt = order.get(self.schema_style)
        if nxt is None:
            return False
        self.schema_style = nxt
        return True


def version_of(model: str) -> tuple[int, int]:
    match = _VERSION.match(model)
    if not match:
        return (0, 0)
    return (int(match.group(1)), int(match.group(2) or 0))


def default_caps(model: str) -> ModelCaps:
    major, minor = version_of(model)
    if (major, minor) == (2, 5):
        return ModelCaps(thinking_style="budget")
    if major >= 3 or major == 0:  # 0 = alias such as "gemini-flash-latest" -> assume newest family
        return ModelCaps()
    return ModelCaps(thinking_style="none")


@dataclass
class ModelHealth:
    name: str
    caps: ModelCaps
    state: str = "closed"  # closed | open
    open_until: float = 0.0
    consecutive_failures: int = 0
    probing: bool = False
    last_error: str | None = None
    last_error_at: float | None = None
    last_success_at: float | None = None
    successes: int = 0
    failures: int = 0


def cooldown_seconds(error: GeminiError, consecutive_failures: int) -> float:
    """How long to leave a model alone after ``error``. 0 = do not trip the breaker."""
    kind = error.kind
    n = max(1, consecutive_failures)
    if kind == "model_unavailable":
        return min(30 * 60 * 2 ** (n - 1), 6 * 3600)
    if kind == "quota_exceeded":
        return min(max(error.retry_after or 0.0, 15 * 60), 3600)
    if kind == "rate_limited":
        return min(max(error.retry_after or 15.0, 5.0), 120.0)
    if kind in ("overloaded", "network", "timeout"):
        return min(10 * 2 ** (n - 1), 120)
    if kind in ("empty_response", "malformed_response"):
        return min(5 * 2 ** (n - 3), 60) if n >= 3 else 0.0  # soft failures: only after a streak
    return 0.0  # bad_request / blocked are about the request, not the model


@dataclass
class ModelRegistry:
    quality: tuple[str, ...] = QUALITY_CHAIN
    fast: tuple[str, ...] = FAST_CHAIN
    clock: Callable[[], float] = time.monotonic
    _health: dict[str, ModelHealth] = field(default_factory=dict)
    _discovered: dict[str, dict[str, Any]] | None = None
    _discovered_at: float | None = None

    # ---- health bookkeeping ---------------------------------------------------------
    def health(self, model: str) -> ModelHealth:
        if model not in self._health:
            self._health[model] = ModelHealth(name=model, caps=default_caps(model))
        return self._health[model]

    def caps(self, model: str) -> ModelCaps:
        return self.health(model).caps

    def is_usable(self, model: str) -> bool:
        h = self.health(model)
        if h.state == "closed":
            return True
        return self.clock() >= h.open_until and not h.probing

    def begin_attempt(self, model: str, *, force: bool = False) -> bool:
        """Claim the model. For a paused model only one caller at a time gets to probe it."""
        h = self.health(model)
        if h.state == "closed":
            return True
        if (force or self.clock() >= h.open_until) and not h.probing:
            h.probing = True
            return True
        return False

    def record_success(self, model: str) -> None:
        h = self.health(model)
        h.state, h.open_until, h.probing = "closed", 0.0, False
        h.consecutive_failures = 0
        h.last_success_at = self.clock()
        h.successes += 1

    def record_failure(self, model: str, error: GeminiError) -> None:
        h = self.health(model)
        h.probing = False
        h.failures += 1
        h.last_error = error.summary
        h.last_error_at = self.clock()
        if error.kind in ("bad_request", "blocked"):
            return  # says nothing about the model's health
        h.consecutive_failures += 1
        cooldown = cooldown_seconds(error, h.consecutive_failures)
        if cooldown > 0:
            h.state = "open"
            h.open_until = self.clock() + cooldown

    def release(self, model: str) -> None:
        """Give back a probe slot without recording an outcome (e.g. the caller was cancelled)."""
        self.health(model).probing = False

    # ---- chains ---------------------------------------------------------------------
    def configured(self, profile: str) -> tuple[str, ...]:
        return self.fast if profile == "fast" else self.quality

    def chain(self, profile: str) -> list[str]:
        """Full ordered preference list for a profile (breaker state NOT applied)."""
        configured = list(self.configured(profile))
        if self._discovered is None:
            return configured
        listed = [m for m in configured if m in self._discovered]
        unlisted = [m for m in configured if m not in self._discovered]
        extras = self._discovered_extras(set(configured), prefer_lite=(profile == "fast"))
        return listed + extras + unlisted

    def candidates(self, profile: str) -> list[str]:
        """Models worth trying right now, best first."""
        return [m for m in self.chain(profile) if self.is_usable(m)]

    def earliest_retry(self, profile: str) -> float:
        """Seconds until some model in the chain becomes usable again (for Retry-After hints)."""
        now = self.clock()
        waits = [max(0.0, self.health(m).open_until - now) for m in self.chain(profile)]
        return min(waits) if waits else 0.0

    def force_candidate(self, profile: str, max_wait: float = 30.0) -> list[str]:
        """Everything is paused. If some pause is about to end anyway, probe that model now rather than
        failing a user request; a model paused for hours (retired / out of quota) is left alone."""
        chain = self.chain(profile)
        if not chain:
            return []
        soonest = min(chain, key=lambda m: self.health(m).open_until)
        return [soonest] if self.health(soonest).open_until - self.clock() <= max_wait else []

    # ---- discovery ------------------------------------------------------------------
    def apply_discovery(self, models: list[dict[str, Any]]) -> None:
        found: dict[str, dict[str, Any]] = {}
        for entry in models:
            name = str(entry.get("name", "")).removeprefix("models/")
            if name and "generateContent" in (entry.get("supportedGenerationMethods") or []):
                found[name] = entry
        if not found:
            return  # an empty list is more likely an API hiccup than reality - keep the static chain
        self._discovered = found
        self._discovered_at = self.clock()
        for name, entry in found.items():
            if entry.get("thinking") is False:
                self.health(name).caps.thinking_style = "none"

    def needs_discovery(self, max_age_seconds: float = 6 * 3600) -> bool:
        return self._discovered_at is None or self.clock() - self._discovered_at > max_age_seconds

    def _discovered_extras(self, known: set[str], *, prefer_lite: bool) -> list[str]:
        extras = [m for m in (self._discovered or {}) if m not in known and _GA_FLASH.match(m)]
        # newest version first; within a version Flash before Flash-Lite (reversed for the fast profile)
        return sorted(extras, key=lambda m: (version_of(m), m.endswith("-lite") == prefer_lite), reverse=True)

    # ---- diagnostics ----------------------------------------------------------------
    def snapshot(self, profile: str = "quality") -> list[dict[str, Any]]:
        now = self.clock()
        rows = []
        for model in self.chain(profile):
            h = self.health(model)
            rows.append(
                {
                    "model": model,
                    "state": "available" if self.is_usable(model) else "paused",
                    "resumes_in_seconds": round(max(0.0, h.open_until - now)) if h.state == "open" else 0,
                    "listed_by_api": None if self._discovered is None else model in self._discovered,
                    "last_error": h.last_error,
                    "successes": h.successes,
                    "failures": h.failures,
                }
            )
        return rows
