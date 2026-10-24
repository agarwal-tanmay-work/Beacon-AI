"""Uniform error responses.

Every error leaves the API as ``{"detail": "<human readable>", "code": "<machine readable>"}`` so the
frontends can react to specific situations (``ai_unavailable``, ``rate_limited`` ...) without parsing
English text. Internal details (SQL, stack traces, upstream bodies, user input) never reach the client.
"""

from typing import Any

import structlog
from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = structlog.get_logger(__name__)


class AppError(Exception):
    """An expected, client-visible failure."""

    def __init__(
        self,
        status_code: int,
        code: str,
        message: str,
        *,
        retry_after: float | None = None,
        extra: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.retry_after = retry_after
        self.extra = extra or {}

    def headers(self) -> dict[str, str]:
        if self.retry_after is None:
            return {}
        return {"Retry-After": str(max(1, int(round(self.retry_after))))}

    def body(self) -> dict[str, Any]:
        body: dict[str, Any] = {"detail": self.message, "code": self.code}
        if self.retry_after is not None:
            body["retry_after"] = max(1, int(round(self.retry_after)))
        body.update(self.extra)
        return body


async def app_error_handler(_request: Request, exc: AppError) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content=exc.body(), headers=exc.headers())


async def http_exception_handler(_request: Request, exc: StarletteHTTPException) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
        headers=getattr(exc, "headers", None) or None,
    )


async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    # Report *where* validation failed, never *what* was submitted (it may be a secret key or a report).
    problems = [
        {"field": ".".join(str(part) for part in err.get("loc", ()) if part != "body"), "message": err.get("msg", "invalid")}
        for err in exc.errors()
    ]
    logger.info("validation_error", path=request.url.path, fields=[p["field"] for p in problems])
    return JSONResponse(status_code=422, content={"detail": "Invalid request.", "code": "validation_error", "errors": problems})


async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.error(
        "unhandled_exception",
        path=request.url.path,
        method=request.method,
        error_type=type(exc).__name__,
        exc_info=exc,
    )
    return JSONResponse(status_code=500, content={"detail": "An unexpected error occurred. Please try again.", "code": "internal_error"})
