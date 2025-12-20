import httpx
import json
import structlog
from typing import Optional, Dict, Any, Type, TypeVar
from pydantic import BaseModel
from app.core.config import settings
from app.schemas.ai import AIAnalysisResult, AICredibilityScore

logger = structlog.get_logger()
T = TypeVar("T", bound=BaseModel)

class GeminiService:
    """
    Isolated stateless service for interacting with Google Gemini API.
    Enforces timeouts, error handling, and output parsing.
    NEVER stores data.
    """
    
    BASE_URL = "https://generativelanguage.googleapis.com/v1/models/gemini-2.5-flash:generateContent"
    TIMEOUT = 10.0 # Strict timeout

    @classmethod
    async def _call_gemini(cls, prompt: str, schema_class: Optional[Type[T]] = None) -> Optional[T | str]:
        """
        Private safe wrapper for HTTP calls.
        """
        if not settings.GEMINI_API_KEY:
            logger.warning("gemini_api_key_missing")
            return None

        headers = {"Content-Type": "application/json"}
        params = {"key": settings.GEMINI_API_KEY}
        
        # Defensive Prompting for JSON
        final_prompt = prompt
        if schema_class:
            final_prompt += f"\n\nReturn strictly valid JSON matching this schema: {schema_class.model_json_schema()}"

        payload = {
            "contents": [{"parts": [{"text": final_prompt}]}],
            "generationConfig": {
                "temperature": 0.2, # Low temperature for deterministic behavior
                "maxOutputTokens": 1024,
            }
        }

        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    cls.BASE_URL, 
                    headers=headers, 
                    params=params, 
                    json=payload, 
                    timeout=cls.TIMEOUT
                )
                if response.status_code != 200:
                    logger.error("gemini_api_error", status=response.status_code, body=response.text[:500])
                    return None
                    
                data = response.json()
                
                # Safe Parsing
                try:
                    text_content = data["candidates"][0]["content"]["parts"][0]["text"]
                    
                    if schema_class:
                        # Attempt to clean JSON markdown if present
                        clean_json = text_content.replace("```json", "").replace("```", "").strip()
                        return schema_class.model_validate_json(clean_json)
                    
                    return text_content
                    
                except (KeyError, IndexError, json.JSONDecodeError) as e:
                    logger.error("gemini_parse_error", error=str(e), response=data)
                    return None
                    
            except httpx.HTTPError as e:
                logger.error("gemini_request_failed", error=str(e))
                return None
            except Exception as e:
                logger.error("gemini_unexpected_error", error=str(e))
                return None

    @classmethod
    async def analyze_report(cls, report_text: str) -> Optional[AIAnalysisResult]:
        """
        Analyzes a report for entities, categorization, and language.
        """
        prompt = (
            "Analyze the following corruption report text. "
            "Extract key entities, detect the language, and estimate the corruption type. "
            "Provide a brief summary.\n\n"
            f"Report Text: {report_text}"
        )
        return await cls._call_gemini(prompt, AIAnalysisResult)

    @classmethod
    async def calculate_credibility(cls, report_text: str, metadata: Dict[str, Any]) -> AICredibilityScore:
        """
        Estimates credibility based on detail level, consistency, and metadata.
        Does NOT judge truthfulness, only data quality.
        """
        prompt = (
            "Assess the credibility of this report based on detail richness, internal consistency, "
            "and provided metadata. Return a score 0-100 where 100 is highly detailed and consistent. "
            "Provide reasoning.\n\n"
            f"Report: {report_text}\n"
            f"Metadata: {json.dumps(metadata)}"
        )
        result = await cls._call_gemini(prompt, AICredibilityScore)
        if not result:
            return AICredibilityScore(score=0, reasoning="AI Service Unavailable")
        return result

    @classmethod
    async def translate_to_english(cls, text: str) -> str:
        """
        Translates text to English if not already.
        """
        prompt = f"Translate the following text to English. If it is already English, return it exactly as is.\n\nText: {text}"
        result = await cls._call_gemini(prompt)
        return str(result) if result else text
