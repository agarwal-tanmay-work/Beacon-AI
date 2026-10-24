"""Gemini access layer: error taxonomy, model registry + circuit breaker, and the REST client."""

from app.services.gemini.client import GeminiClient, GenerationRequest, GenerationResult, gemini
from app.services.gemini.errors import (
    GeminiAuthError,
    GeminiBlocked,
    GeminiError,
    GeminiNotConfigured,
    GeminiUnavailable,
)
from app.services.gemini.schema import make_parser, schema_for

__all__ = [
    "GeminiAuthError",
    "GeminiBlocked",
    "GeminiClient",
    "GeminiError",
    "GeminiNotConfigured",
    "GeminiUnavailable",
    "GenerationRequest",
    "GenerationResult",
    "gemini",
    "make_parser",
    "schema_for",
]
