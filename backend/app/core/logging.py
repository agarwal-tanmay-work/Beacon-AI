"""Structured logging with secret redaction.

Two rules protect reporters and credentials:
  * keys, tokens and passwords are masked before a log line is written (the repository history
    contains API keys that leaked through logged request URLs);
  * message bodies / evidence text are never passed to the logger - only metadata.
"""

import logging
import re
import sys
from typing import Any

import structlog

from app.core.config import settings

_SENSITIVE_FIELD_NAMES = frozenset(
    {
        "secret_key",
        "access_token",
        "token",
        "password",
        "authorization",
        "api_key",
        "apikey",
        "x-goog-api-key",
        "service_role_key",
        "admin_password",
        "admin_password_hash",
        "sig",
        "signature",
    }
)

# Anything that looks like a credential inside a free-text value.
_SECRET_IN_TEXT = re.compile(
    r"(AIza[0-9A-Za-z_\-]{20,}"  # Google API key
    r"|sb_(?:secret|publishable)_[0-9A-Za-z_\-]+"  # Supabase new-style keys
    r"|eyJ[0-9A-Za-z_\-]{8,}\.[0-9A-Za-z_\-]{8,}\.[0-9A-Za-z_\-]{8,}"  # JWTs
    r"|(?i:(?:api[_-]?key|key|token|sig|password)=)[^&\s\"']+)"
)


def redact(value: str) -> str:
    return _SECRET_IN_TEXT.sub("***", value)


def _redact_processor(_logger: Any, _method: str, event_dict: dict[str, Any]) -> dict[str, Any]:
    for key, value in list(event_dict.items()):
        if key.lower() in _SENSITIVE_FIELD_NAMES:
            event_dict[key] = "***"
        elif isinstance(value, str):
            event_dict[key] = redact(value)
    return event_dict


def setup_logging() -> None:
    """Route structlog *and* stdlib logging (uvicorn, sqlalchemy, httpx, ...) through one pipeline."""
    shared_processors: list[Any] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
        _redact_processor,
    ]

    structlog.configure(
        processors=[*shared_processors, structlog.stdlib.ProcessorFormatter.wrap_for_formatter],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    renderer: Any = structlog.processors.JSONRenderer() if settings.is_production else structlog.dev.ConsoleRenderer(colors=False)
    formatter = structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=shared_processors,
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            structlog.processors.format_exc_info,
            _redact_processor,  # again: tracebacks are only rendered to text at this point
            renderer,
        ],
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)
    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(settings.LOG_LEVEL.upper())

    # httpx logs every request URL at INFO. Quiet it down (the key now travels in a header anyway).
    for noisy in ("httpx", "httpcore", "hpack", "multipart"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
    if not settings.is_production and settings.LOG_LEVEL.upper() != "DEBUG":
        logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    return structlog.stdlib.get_logger(name)
