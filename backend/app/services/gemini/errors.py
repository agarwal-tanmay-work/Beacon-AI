"""Error taxonomy for Gemini calls.

The classification drives the fallback chain, so it matters that each class means one thing:

=====================  ==================================  ========================================
class                  typical cause                       what the client does
=====================  ==================================  ========================================
GeminiNotConfigured    no GEMINI_API_KEY                   fail fast (no network call)
GeminiAuthError        401 / invalid, expired or leaked    stop the whole chain, pause all calls
                       key / unsupported region
GeminiModelUnavailable 404, model retired or not enabled   skip model for a long time
                       for this project (e.g. gemini-2.5)
GeminiQuotaExceeded    daily / spend quota, "limit: 0"     skip model for ~1h
GeminiRateLimited      per-minute 429                      skip model for retry-after seconds
GeminiOverloaded       500 / 502 / 503                     one quick retry, then next model
GeminiTimeout          request deadline hit                next model immediately
GeminiNetworkError     DNS / connect / TLS problems        one quick retry, then next model
GeminiBadRequest       400 (our request was wrong)         adapt the request once, else next model
GeminiBlocked          safety / prohibited content         try one more model, then give up
GeminiEmptyResponse    no text (e.g. MAX_TOKENS in thought) retry / next model
GeminiMalformed        JSON that does not match the schema retry / next model
GeminiUnavailable      every model failed                  raised to the caller (-> basic mode)
=====================  ==================================  ========================================
"""

from dataclasses import dataclass


class GeminiError(Exception):
    """Base class. ``retry_after`` (seconds) is a hint from the API when it gave one."""

    kind = "error"

    def __init__(self, message: str = "", *, status_code: int | None = None, retry_after: float | None = None):
        super().__init__(message or self.kind)
        self.status_code = status_code
        self.retry_after = retry_after
        # True when the answer was cut off by maxOutputTokens (thinking tokens count towards it).
        self.truncated = False

    @property
    def summary(self) -> str:
        return f"{self.kind}({self.status_code or '-'})"


class GeminiNotConfigured(GeminiError):
    kind = "not_configured"


class GeminiAuthError(GeminiError):
    kind = "auth"


class GeminiModelUnavailable(GeminiError):
    kind = "model_unavailable"


class GeminiQuotaExceeded(GeminiError):
    kind = "quota_exceeded"


class GeminiRateLimited(GeminiError):
    kind = "rate_limited"


class GeminiOverloaded(GeminiError):
    kind = "overloaded"


class GeminiTimeout(GeminiError):
    kind = "timeout"


class GeminiNetworkError(GeminiError):
    kind = "network"


class GeminiBadRequest(GeminiError):
    """HTTP 400. ``adaptation`` names the request feature the API complained about, if we can tell."""

    kind = "bad_request"

    def __init__(self, message: str = "", *, status_code: int | None = 400, adaptation: str | None = None):
        super().__init__(message, status_code=status_code)
        self.adaptation = adaptation  # "thinking" | "schema" | None


class GeminiBlocked(GeminiError):
    kind = "blocked"

    def __init__(self, reason: str, *, status_code: int | None = None):
        super().__init__(f"blocked: {reason}", status_code=status_code)
        self.reason = reason


class GeminiEmptyResponse(GeminiError):
    kind = "empty_response"


class GeminiMalformedResponse(GeminiError):
    kind = "malformed_response"


@dataclass
class Attempt:
    """One try against one model - kept for logs and for the 'all models failed' report."""

    model: str
    outcome: str  # "ok" or an error ``kind``
    status_code: int | None = None
    latency_ms: int = 0
    detail: str = ""


class GeminiUnavailable(GeminiError):
    """Every candidate model failed (or the breaker had all of them paused)."""

    kind = "unavailable"

    def __init__(self, attempts: list[Attempt], *, retry_after: float | None = None, blocked: bool = False):
        tried = ", ".join(f"{a.model}:{a.outcome}" for a in attempts) or "no model available"
        super().__init__(f"all Gemini models failed ({tried})", retry_after=retry_after)
        self.attempts = attempts
        self.blocked = blocked
