import httpx
import json
import structlog
from typing import Optional, Dict, Any, Type, TypeVar, List
from pydantic import BaseModel
from app.core.config import settings
from app.schemas.ai import AIAnalysisResult, CredibilityFeatures
import base64

logger = structlog.get_logger()
T = TypeVar("T", bound=BaseModel)

class GroqService:
    """
    Service for interacting with Groq Cloud API (Llama 3 models).
    Fast, efficient, and stateless.
    """
    
    BASE_URL = "https://api.groq.com/openai/v1/chat/completions"
    TIMEOUT = 60.0 # Increased for stability during complex scoring 
    
    # Models
    TEXT_MODEL = "llama-3.3-70b-versatile"
    VISION_MODEL = "llama-3.2-11b-vision-preview"

    @classmethod
    async def _call_groq(cls, messages: List[Dict[str, Any]], schema_class: Optional[Type[T]] = None, model: str = TEXT_MODEL) -> Optional[T | str]:
        """
        Private safe wrapper for Groq HTTP calls.
        """
        if not settings.GROQ_API_KEY:
            logger.warning("groq_api_key_missing")
            return None

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {settings.GROQ_API_KEY}"
        }
        
        # JSON Schema Enforcement (Manual via System Prompt for Llama 3)
        # Llama 3 is good at following JSON instructions, but we enforce it.
        if schema_class:
            system_instruction = f"You must output STRICT VALID JSON matching this schema: {schema_class.model_json_schema()}"
            # Prepend system instruction
            messages.insert(0, {"role": "system", "content": system_instruction})
            
        payload = {
            "model": model,
            "messages": messages,
            "temperature": 0.2,
            "max_tokens": 1024,
        }
        
        # Only add response_format for JSON mode - Groq doesn't support "text" type
        if schema_class:
            payload["response_format"] = {"type": "json_object"}

        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    cls.BASE_URL, 
                    headers=headers, 
                    json=payload, 
                    timeout=cls.TIMEOUT
                )
                
                if response.status_code != 200:
                    logger.error("groq_api_error", status=response.status_code, body=response.text[:500])
                    return None
                    
                data = response.json()
                content = data["choices"][0]["message"]["content"]
                
                if schema_class:
                    try:
                        return schema_class.model_validate_json(content)
                    except Exception as e:
                        logger.error("groq_parse_error", error=str(e), content=content)
                        return None
                        
                return content

            except Exception as e:
                logger.error("groq_request_failed", error=str(e))
                print(f"[GroqService] ❌ REQUEST FAILED: {e}")
                return None

    @classmethod
    async def analyze_report(cls, report_text: str) -> Optional[AIAnalysisResult]:
        messages = [{
            "role": "user", 
            "content": (
                "Analyze the following corruption report text. "
                "Extract key entities, detect the language, and estimate the corruption type. "
                "Provide a brief summary.\n\n"
                f"Report Text: {report_text}"
            )
        }]

        print(f"[GroqService] Analyzing Report: {report_text[:50]}...")
        return await cls._call_groq(messages, AIAnalysisResult)

    @classmethod
    async def extract_credibility_features(
        cls, 
        chat_history: List[Dict[str, str]], 
        evidence_summary: str, 
        metadata: Dict[str, Any]
    ) -> Optional[CredibilityFeatures]:
        
        role_definition = """
You are an expert Intelligence Analyst for Beacon AI.
Your task is to EXTRACT structured features from corruption reports to enable downstream credibility scoring.

DO NOT CALCULATE A SCORE.
Instead, assess the following dimensions objectively:

1. Information Completeness:
   - Identify if key W-questions (What, Where, When, How, Who) are present.
   - Classify overall clarity (Vague vs Specific).

2. Consistency:
   - Check for contradictions or incoherence.
   - Classify the flow (Contradictory -> Fully Coherent).

3. Evidence Quality (Assessment):
   - Assess the description of evidence provided (if any).
   - Is it relevant? Strong/Direct? Or Weak?
   - Suspect tampering?

4. Tone:
   - Classify tone (Aggressive, Emotional, or Calm/Factual).

5. Temporal Extraction:
   - Extract the specific Incident Date if mentioned (ISO format YYYY-MM-DD).

6. Malicious Check:
   - Flag potential Spam, Vendetta, or Fake indicators.

7. User Cooperation:
   - Assess if the user answered follow-up questions cooperatively.

OUTPUT format: Strict JSON matching the provided schema.
"""

        conversation_text = "\n".join([f"{msg['role'].upper()}: {msg['content']}" for msg in chat_history])
        
        messages = [
            {"role": "system", "content": role_definition},
            {
                "role": "user", 
                "content": (
                    "Extract credibility features from this report:\n\n"
                    f"Conversation Log:\n{conversation_text}\n\n"
                    f"Evidence Analysis Summary:\n{evidence_summary}\n\n"
                    f"Metadata:\n{json.dumps(metadata, default=str)}"
                )
            }
        ]
        
        return await cls._call_groq(messages, CredibilityFeatures)


    @classmethod
    async def translate_to_english(cls, text: str) -> str:
        messages = [{
            "role": "user",
            "content": f"Translate the following text to English. If it is already English, return it exactly as is.\n\nText: {text}"
        }]
        result = await cls._call_groq(messages)
        return str(result) if result else text

    @classmethod
    async def analyze_evidence(cls, file_bytes: bytes, mime_type: str) -> Dict[str, Any]:
        """
        Analyzes evidence (image) using Llama 3.2 Vision.
        """
        b64_image = base64.b64encode(file_bytes).decode('utf-8')
        image_url = f"data:{mime_type};base64,{b64_image}"
        
        prompt = "Analyze this image in the context of a corruption report. Describe what is shown, identifying visible text (OCR) and any signs of digital manipulation. Assess its relevance as evidence."

        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": image_url
                        }
                    }
                ]
            }
        ]
        
        # Use Vision Model
        result_text = await cls._call_groq(messages, model=cls.VISION_MODEL)
        
        return {"analysis": result_text if result_text else "Analysis failed"}

    @classmethod
    async def generate_pro_summary(cls, chat_history: List[Dict[str, str]]) -> str:
        conversation_text = "\n".join([f"{msg['role'].upper()}: {msg['content']}" for msg in chat_history])
        messages = [{
            "role": "user",
            "content": (
                "You are a professional intelligence analyst. Write a detailed summary of this corruption report.\n"
                "CRITICAL RULES:\n"
                "1. PRESERVE EVERY SINGLE DETAIL provided by the user (dates, times, locations, names, amounts, clothing, dialogue, etc). Do not omit anything.\n"
                "2. ANONYMIZE the Victim/Reporter: Redact their name or personal identifiers if mentioned (e.g., use 'reporting party').\n"
                "3. EXPOSE the Perpetrator: Include the full name and details of the corrupt official/person exactly as stated.\n"
                "4. ZERO FLUFF: Do not add intro/outro or AI interpretation. Write only the facts from the user's input.\n\n"
                "If the user provided absolutely no details (empty conversation), state 'Insufficient information provided by the reporter.' "
                "However, if there is ANY detail (e.g., 'Policeman asked for bribe'), summarize that fully.\n\n"
                f"Conversation Log:\n{conversation_text}"
            )
        }]
        result = await cls._call_groq(messages)
        return str(result)

    @classmethod
    async def calculate_scoring_rubric(
        cls, 
        chat_history: List[Dict[str, str]], 
        evidence_summary: str, 
        metadata: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Calculates credibility score and explanation using the User's strict rubric.
        """
        
        class ScoringResult(BaseModel):
            score: int
            explanation: str
            breakdown: Dict[str, int]
        
        conversation_text = "\n".join([f"{msg['role'].upper()}: {msg['content']}" for msg in chat_history])
        
        rubric_prompt = """
Design a credibility scoring engine for Beacon AI that assigns each corruption report an explainable score from 1 to 100 based strictly on user-provided information only.
The score must consider completeness of details (what, where, when, how), internal consistency of the narrative, quality and relevance of any uploaded evidence (images, documents, videos, audio, OCR and tamper signals), tone and language sincerity, time gap between incident and reporting, similarity or corroboration with past anonymized reports, and the user’s responsiveness to follow-up questions. Apply negative penalties for indicators of spam, fabrication, defamation, automation, or manipulated evidence, but never penalize anonymity or lack of evidence alone. Do not infer, assume, or add facts. The score must reflect reliability and actionability, not legal truth or guilt, and must include a concise neutral justification suitable for authority review while respecting privacy, ethics, and non-bias principles.

OUTPUT JSON FORMAT:
{
    "score": <integer 1-100>,
    "explanation": "<concise neutral justification>",
    "breakdown": {
        "completeness": <score>,
        "consistency": <score>,
        "evidence": <score>,
        "tone": <score>,
        "temporal": <score>,
        "penalties": <negative_score>
    }
}
"""

        messages = [
            {"role": "system", "content": rubric_prompt},
            {
                "role": "user", 
                "content": (
                    "Calculate the Credibility Score based on this report:\n\n"
                    f"Conversation Log:\n{conversation_text}\n\n"
                    f"Evidence Summary:\n{evidence_summary}\n\n"
                    f"Metadata:\n{json.dumps(metadata, default=str)}"
                )
            }
        ]
        
        result = await cls._call_groq(messages, ScoringResult)
        if result:
            return result.model_dump()
            
        # Strict Mode: Return None on failure. No defaults.
        return None

