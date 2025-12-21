import httpx
import json
import structlog
from typing import Optional, Dict, Any, Type, TypeVar, List
from pydantic import BaseModel
from app.core.config import settings
from app.schemas.ai import AIAnalysisResult, CredibilityFeatures, ScoringResult
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
    ) -> Optional[Dict[str, Any]]:
        """
        Calculates credibility score and explanation using the User's strict 1-100 rubric.
        Dimensions:
        1. information_completeness (0–20)
        2. internal_consistency (0–15)
        3. evidence_quality (0–25)
        4. language_tone (0–10)
        5. temporal_proximity (0–10)
        6. corroboration_patterns (0–10)
        7. user_cooperation (0–5)
        8. malicious_penalty (−15 to 0)
        """
        
        conversation_text = "\n".join([f"{msg['role'].upper()}: {msg['content']}" for msg in chat_history])
        
        role_definition = """
You are an expert AI credibility assessment engine for Beacon AI, a government-grade, privacy-first corruption reporting chatbot.
Your task is to generate a credibility score between 1 and 100 for a corruption report.

STRICT RULES:
1. Use ONLY the provided information (chat history, evidence summary, metadata).
2. Do NOT invent, assume, infer, or add any facts.
3. Do NOT penalize a user for anonymity.
4. Do NOT use political, personal, caste, religion, gender, or ideology bias.
5. The score must be explainable, structured, and defensible.
6. Higher score = higher reliability and actionability, NOT guilt or legal truth.
7. Do NOT make legal judgments.
8. Score reflects reliability/actionability, not verdict.

SCORING FRAMEWORK:
1. INFORMATION COMPLETENESS (0–20):
   - 0–5: Extremely vague, missing most elements
   - 6–10: Some details present, major gaps
   - 11–15: Most details present, minor gaps
   - 16–20: Clear, specific, structured description

2. INTERNAL CONSISTENCY & LOGICAL FLOW (0–15):
   - 0–5: Contradictory or incoherent
   - 6–10: Mostly consistent with minor ambiguity
   - 11–15: Fully coherent and stable

3. EVIDENCE PRESENCE & QUALITY (0–25):
   - 0: No evidence provided
   - 1–8: Weak or unclear evidence
   - 9–17: Relevant but partial or indirect evidence
   - 18–25: Strong, direct, high-quality supporting evidence
   (Absence of evidence != false report)

4. LANGUAGE & TONE ANALYSIS (0–10):
   - 0–3: Highly aggressive, incoherent, or sensational
   - 4–7: Emotionally charged but understandable
   - 8–10: Calm, factual, sincere

5. TEMPORAL PROXIMITY (0–10):
   - 0–3: Very old with vague timing
   - 4–7: Moderate delay but clear timeline
   - 8–10: Very recent and well-timestamped

6. CORROBORATION & PATTERN MATCHING (0–10):
   - 0–3: No overlap or unique case
   - 4–7: Partial similarity with past reports
   - 8–10: Strong pattern match with multiple reports

7. USER COOPERATION & RESPONSIVENESS (0–5):
   - 0–2: Avoids questions or provides evasive answers
   - 3–4: Answers most questions adequately
   - 5: Fully cooperative and responsive

8. MALICIOUS / SPAM / DEFAMATION CHECK (-15 to 0):
   - 0: No malicious indicators
   - -5: Mild concern
   - -10: Strong concern
   - -15: Severe credibility risk
   (Flags: personal vendetta, unsupported accusations, copy-paste, fake evidence, bot behavior)

FINAL SCORE CALCULATION:
- Sum all positive dimensions (1-7)
- Subtract penalties (8)
- Clamp final result strictly between 1 and 100. Never return 0.
"""

        messages = [
            {"role": "system", "content": role_definition},
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
            # Manual Clamp check just in case Llama messed up the math
            res_dict = result.model_dump()
            score = res_dict["credibility_score"]
            res_dict["credibility_score"] = max(1, min(100, score))
            return res_dict
            
        return None

