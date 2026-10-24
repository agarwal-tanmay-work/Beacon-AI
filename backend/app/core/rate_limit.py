"""In-memory abuse protection.

* ``SlidingWindowLimiter`` - at most N hits per key per window (create session, chat, uploads ...)
* ``FailureLimiter``       - lock a key out after N *failed* attempts (login, secret-key guessing)

State lives in process memory: it resets on restart and is per-instance when scaled horizontally.
That is a deliberate trade-off for a single-instance Render service; the global caps below still
bound the damage a distributed attacker can do to the Gemini quota.
"""

import ipaddress
import time
from collections import deque
from collections.abc import Callable

from fastapi import Request

from app.core.config import settings
from app.core.exceptions import AppError

Clock = Callable[[], float]


class SlidingWindowLimiter:
    def __init__(self, limit: int, window_seconds: float, *, max_keys: int = 20_000, clock: Clock = time.monotonic):
        self.limit = limit
        self.window = window_seconds
        self.max_keys = max_keys
        self._clock = clock
        self._events: dict[str, deque[float]] = {}

    def _window_events(self, key: str, now: float) -> deque[float]:
        events = self._events.setdefault(key, deque())
        cutoff = now - self.window
        while events and events[0] <= cutoff:
            events.popleft()
        return events

    def _evict_if_needed(self, now: float) -> None:
        if len(self._events) <= self.max_keys:
            return
        for key in [k for k in self._events if not self._window_events(k, now)]:
            del self._events[key]
        while len(self._events) > self.max_keys:  # still too many: drop the oldest keys
            del self._events[next(iter(self._events))]

    def retry_after(self, key: str) -> float:
        """Seconds until ``key`` is below the limit again (0.0 when it already is). Read-only."""
        now = self._clock()
        events = self._window_events(key, now)
        if len(events) >= self.limit:
            return max(0.0, events[0] + self.window - now)
        return 0.0

    def record(self, key: str) -> None:
        now = self._clock()
        self._evict_if_needed(now)
        self._window_events(key, now).append(now)

    def hit(self, key: str) -> tuple[bool, float]:
        """Register a hit if allowed. Returns ``(allowed, retry_after_seconds)``."""
        wait = self.retry_after(key)
        if wait > 0:
            return False, wait
        self.record(key)
        return True, 0.0

    def reset(self, key: str | None = None) -> None:
        if key is None:
            self._events.clear()
        else:
            self._events.pop(key, None)


class FailureLimiter:
    """Counts failures; once ``max_failures`` happened inside the window the key is blocked."""

    def __init__(self, max_failures: int, window_seconds: float, *, clock: Clock = time.monotonic):
        self._window = SlidingWindowLimiter(max_failures, window_seconds, clock=clock)

    def blocked_for(self, key: str) -> float:
        return self._window.retry_after(key)

    def record_failure(self, key: str) -> None:
        self._window.record(key)

    def reset(self, key: str | None = None) -> None:
        self._window.reset(key)


# --------------------------------------------------------------------------------------
# Rule registry - (limit, window seconds). Per client unless noted.
# --------------------------------------------------------------------------------------
_RULES: dict[str, tuple[int, float]] = {
    "create_report": (12, 3600),
    "send_message": (45, 600),
    "upload": (30, 3600),
    "track": (40, 900),
    "track_write": (40, 900),
}
# Absolute ceilings across ALL clients (protects the Gemini quota from a distributed flood).
_GLOBAL_RULES: dict[str, tuple[int, float]] = {
    "create_report": (300, 3600),
    "send_message": (240, 60),
    "upload": (600, 3600),
}

_limiters = {name: SlidingWindowLimiter(*rule) for name, rule in _RULES.items()}
_global_limiters = {name: SlidingWindowLimiter(*rule) for name, rule in _GLOBAL_RULES.items()}

login_failures = FailureLimiter(max_failures=6, window_seconds=900)
track_ip_failures = FailureLimiter(max_failures=15, window_seconds=900)
track_case_failures = FailureLimiter(max_failures=30, window_seconds=900)


def reset_all() -> None:
    """Clear every counter (used by tests)."""
    for limiter in (*_limiters.values(), *_global_limiters.values()):
        limiter.reset()
    for failures in (login_failures, track_ip_failures, track_case_failures):
        failures.reset()


def client_ip(request: Request) -> str:
    """Best-effort client IP. Behind Vercel -> Render the left-most X-Forwarded-For entry is the visitor."""
    if settings.TRUST_PROXY_HEADERS:
        first = request.headers.get("x-forwarded-for", "").split(",")[0].strip()
        if first:
            try:
                return str(ipaddress.ip_address(first))
            except ValueError:
                pass
    return request.client.host if request.client else "unknown"


def raise_if_blocked(retry_after: float, *, message: str = "Too many attempts. Please wait a few minutes and try again.") -> None:
    if retry_after > 0:
        raise AppError(429, "rate_limited", message, retry_after=retry_after)


def enforce(rule: str, request: Request, *, extra_key: str | None = None) -> None:
    """Apply a named rule to the calling client (and optionally to a secondary key such as a report id)."""
    if not settings.RATE_LIMIT_ENABLED:
        return
    keys = [f"{rule}:{client_ip(request)}"]
    if extra_key:
        keys.append(f"{rule}:{extra_key}")
    for key in keys:
        allowed, retry_after = _limiters[rule].hit(key)
        if not allowed:
            raise AppError(429, "rate_limited", "Too many requests. Please slow down and try again shortly.", retry_after=retry_after)
    if rule in _global_limiters:
        allowed, retry_after = _global_limiters[rule].hit("global")
        if not allowed:
            raise AppError(
                429,
                "rate_limited",
                "The service is receiving a lot of traffic right now. Please try again in a moment.",
                retry_after=retry_after,
            )


def limit(rule: str) -> Callable[[Request], None]:
    """FastAPI dependency factory: ``Depends(limit("upload"))``."""

    def dependency(request: Request) -> None:
        enforce(rule, request)

    return dependency
