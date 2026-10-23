import httpx
import json
import structlog
import base64
import traceback
from typing import Optional, Dict, Any, Type, TypeVar, List, Tuple
from pydantic import BaseModel
from app.core.config import settings
from app.schemas.ai import AIAnalysisResult, EvidenceMetadata, ScoringResult

logger = structlog.get_logger()
T = TypeVar("T", bound=BaseModel)

SMART_MODELS = [
    'gemini-3.8-flash',
    'gemini-3.5-flash',
    'gemini-flash-latest',
    'gemini-3.5-flash-lite',
    'gemini-3.1-flash-lite',
    'gemini-flash-lite-latest',
]

FAST_MODELS = [
    'gemini-3.5-flash-lite',
    'gemini-flash-lite-latest',
    'gemini-3.1-flash-lite',
    'gemini-3.5-flash',
    'gemini-flash-latest',
]


class GeminiService:
    """
    Unified service for interacting with Google Gemini API.
    Handles both text generation and vision/image analysis.
    Using the configured Gemini smart model list.
    """

    # Default model = first smart model from the configured list
    TEXT_MODEL = SMART_MODELS[0]
    VISION_MODEL = SMART_MODELS[0]  # Same model supports multimodal

    BASE_URL = "https://generativelanguage.googleapis.com/v1beta/models"
    TIMEOUT = 30.0
