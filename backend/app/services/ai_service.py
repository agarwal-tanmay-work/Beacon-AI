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


class GeminiService:
    """
    Unified service for interacting with Google Gemini API.
    Handles both text generation and vision/image analysis.
    Using Gemini 2.5 Flash model.
    """
    
    # Gemini 3.0 Flash model (Preview)
    TEXT_MODEL = "gemini-3-flash-preview"
    VISION_MODEL = "gemini-3-flash-preview"  # Same model supports multimodal
    
    BASE_URL = "https://generativelanguage.googleapis.com/v1beta/models"
    TIMEOUT = 30.0
    
    _client: Optional[httpx.AsyncClient] = None

    @classmethod
    async def get_client(cls) -> httpx.AsyncClient:
        if cls._client is None or cls._client.is_closed:
            cls._client = httpx.AsyncClient(timeout=cls.TIMEOUT)
        return cls._client

    @classmethod
    async def close_client(cls):
        if cls._client and not cls._client.is_closed:
            await cls._client.aclose()
            cls._client = None

    @classmethod
    async def _call_gemini(
        cls, 
        contents: List[Dict[str, Any]], 
        schema_class: Optional[Type[T]] = None, 
        model: str = None,
        timeout: Optional[float] = None,
        system_instruction: Optional[str] = None
    ) -> Tuple[Optional[T | str], Optional[int]]:
        """
        Call Gemini API with the given contents.
        Returns: (result, retry_after_seconds)
        """
        if not settings.GEMINI_API_KEY:
            logger.warning("gemini_api_key_missing")
            return None, None
        
        model = model or cls.TEXT_MODEL
        url = f"{cls.BASE_URL}/{model}:generateContent?key={settings.GEMINI_API_KEY}"
        
        # Build payload
        payload = {
            "contents": contents,
            "generationConfig": {
                "temperature": 0.1,
                "maxOutputTokens": 2048,
            }
        }
        
        # Add system instruction if provided
        if system_instruction:
            payload["systemInstruction"] = {
                "parts": [{"text": system_instruction}]
            }
        
        # JSON schema enforcement for structured output
        if schema_class:
            schema_text = f"You must output STRICT VALID JSON matching this schema: {schema_class.model_json_schema()}"
            if system_instruction:
                payload["systemInstruction"]["parts"][0]["text"] = f"{system_instruction}\n\n{schema_text}"
            else:
                payload["systemInstruction"] = {"parts": [{"text": schema_text}]}
            payload["generationConfig"]["responseMimeType"] = "application/json"

        effective_timeout = timeout if timeout is not None else cls.TIMEOUT

        client = await cls.get_client()
        try:
            import asyncio
            
            response = None
            max_retries = 2  # Only 2 attempts total for speed
            
            for attempt in range(max_retries):
                try:
                    response = await client.post(
                        url,
                        json=payload,
                        timeout=effective_timeout
                    )
                    
                    # Handle 429 (rate limit) and 503 (overloaded) with quick retry
                    if response.status_code in (429, 503):
                        retry_after = response.headers.get("Retry-After")
                        # Quick retry: 1s first, 2s second - prioritize speed
                        wait_seconds = min(int(retry_after) if retry_after and retry_after.isdigit() else (attempt + 1), 2)
                        error_type = "gemini_rate_limit" if response.status_code == 429 else "gemini_overloaded"
                        
                        if attempt < max_retries - 1:
                            logger.warning(f"{error_type}_retrying", status=response.status_code, retry_after=wait_seconds)
                            await asyncio.sleep(wait_seconds)
                            continue  # Retry once
                        else:
                            # Final attempt failed, return with retry hint
                            logger.error(f"{error_type}_exhausted", status=response.status_code, retry_after=wait_seconds)
                            return None, wait_seconds
                    
                    # Success - break out of retry loop
                    break
                    
                except (httpx.NetworkError, httpx.TimeoutException) as e:
                    if attempt == max_retries - 1:
                        logger.error("gemini_network_error_final", error=repr(e))
                        return None, None
                    # Quick retry for network errors
                    logger.warning(f"gemini_network_retry_{attempt+1}", error=str(e))
                    await asyncio.sleep(1)
            
            if not response:
                return None, None
            
            if response.status_code != 200:
                logger.error("gemini_api_error", status=response.status_code, body=response.text[:500])
                return None, None
            
            data = response.json()
            
            # Extract content from Gemini response
            try:
                content = data["candidates"][0]["content"]["parts"][0]["text"]
            except (KeyError, IndexError) as e:
                logger.error("gemini_response_parse_error", error=str(e), data=data)
                return None, None
            
            if schema_class:
                try:
                    # Clean up JSON if wrapped in markdown code blocks
                    cleaned = content.strip()
                    if cleaned.startswith("```json"):
                        cleaned = cleaned[7:]
                    if cleaned.startswith("```"):
                        cleaned = cleaned[3:]
                    if cleaned.endswith("```"):
                        cleaned = cleaned[:-3]
                    cleaned = cleaned.strip()
                    return schema_class.model_validate_json(cleaned), None
                except Exception as e:
                    logger.error("gemini_parse_error", error=str(e), content=content[:500])
                    return None, None
            
            return content, None

        except Exception as e:
            logger.error("gemini_request_failed", error=repr(e), traceback=traceback.format_exc())
            return None, None

    @classmethod
    async def analyze_image(cls, image_bytes: bytes, mime_type: str, prompt: str) -> Optional[str]:
        """Analyze an image using Gemini's vision capabilities."""
        if not settings.GEMINI_API_KEY:
            logger.warning("gemini_api_key_missing")
            return None

        b64_image = base64.b64encode(image_bytes).decode('utf-8')
        
        contents = [{
            "parts": [
                {"text": prompt},
                {
                    "inlineData": {
                        "mimeType": mime_type,
                        "data": b64_image
                    }
                }
            ]
        }]

        result, _ = await cls._call_gemini(contents, model=cls.VISION_MODEL)
        return str(result).strip() if result else None

    @classmethod
    async def analyze_report(cls, report_text: str) -> Optional[AIAnalysisResult]:
        contents = [{
            "parts": [{"text": f"Analyze this report. Extract entities, language, and corruption type.\n\nReport: {report_text}"}]
        }]
        result, _ = await cls._call_gemini(contents, AIAnalysisResult)
        return result

    @classmethod
    async def translate_to_english(cls, text: str) -> str:
        contents = [{
            "parts": [{"text": f"Translate to English (return original if already English): {text}"}]
        }]
        result, _ = await cls._call_gemini(contents)
        return str(result) if result else text

    @classmethod
    async def analyze_evidence(cls, file_bytes: bytes, mime_type: str) -> Dict[str, Any]:
        """Analyze image evidence using Gemini vision."""
        prompt = "Analyze this image. Describe visible text and objects."
        result = await cls.analyze_image(file_bytes, mime_type, prompt)
        return {"analysis": result if result else "Visual analysis unavailable"}

    @classmethod
    async def perform_forensic_ocr_analysis(cls, ocr_text: str, narrative_summary: str, timeout: Optional[float] = None) -> Tuple[Optional[Any], Optional[int]]:
        from app.schemas.ai import ForensicOCRAnalysis
        
        system_prompt = """You are a forensic OCR text analysis module within Beacon Credibility Engine.
You DO NOT perform OCR. OCR has already been executed using Tesseract.
You ONLY analyze the extracted text provided to you.

Your task is to:
- Assess the quality and usefulness of the OCR output
- Identify objective, verifiable signals
- Detect relevance to the user's narrative
- Avoid assumptions, interpretations, or legal conclusions

--------------------------------------------------
ANALYSIS RULES (STRICT):
- Do NOT assume missing text implies absence of evidence
- Do NOT infer intent, illegality, or wrongdoing
- Do NOT correct OCR errors unless they are obvious
- Treat low-quality or noisy OCR neutrally, not negatively

--------------------------------------------------
ANALYZE FOR THE FOLLOWING OBJECTIVE SIGNALS:
1. TEXT PRESENCE
2. FACTUAL ELEMENTS (Dates, Monetary amounts, Names, Locations, Official indicators)
3. RELEVANCE ALIGNMENT
4. LIMITATIONS

--------------------------------------------------
FINAL SAFETY RULE:
This analysis reflects OCR text characteristics only.
It does not verify authenticity, truth, or legality of the content.
"""
        contents = [{
            "parts": [{"text": f"--- USER NARRATIVE SUMMARY ---\n{narrative_summary}\n\n--- OCR EXTRACTED TEXT ---\n{ocr_text}"}]
        }]
        return await cls._call_gemini(contents, ForensicOCRAnalysis, timeout=timeout, system_instruction=system_prompt)

    @classmethod
    async def perform_forensic_audio_analysis(cls, transcript_text: str, narrative_summary: str, audio_metadata: dict = None, timeout: Optional[float] = None) -> Tuple[Optional[Any], Optional[int]]:
        from app.schemas.ai import ForensicAudioAnalysis
        
        metadata_str = ""
        if audio_metadata:
            metadata_str = f"TRANSCRIPTION_METADATA:\n- Audio clarity: {audio_metadata.get('clarity', 'unknown')}\n- Duration: {audio_metadata.get('duration_seconds', 'unknown')}s"

        system_prompt = """You are a forensic audio transcription analysis module.
You DO NOT process media files. You ONLY analyze the resulting transcription.

STRICT ANALYSIS RULES:
- Do NOT assume intent or identity.
- Do NOT infer illegality.
- Treat unclear transcription neutrally.

ANALYZE FOR:
1. TRANSCRIPTION USABILITY
2. FACTUAL ELEMENTS (Dates, Money, Names, Locations)
3. NARRATIVE ALIGNMENT
4. AMBIGUITIES
"""
        contents = [{
            "parts": [{"text": f"--- USER NARRATIVE SUMMARY ---\n{narrative_summary}\n\n{metadata_str}\n--- TRANSCRIPTION TEXT ---\n{transcript_text}"}]
        }]
        return await cls._call_gemini(contents, ForensicAudioAnalysis, timeout=timeout, system_instruction=system_prompt)

    @classmethod
    async def perform_forensic_visual_analysis(cls, image_bytes: bytes, mime_type: str, timeout: Optional[float] = None) -> Tuple[Optional[str], Optional[int]]:
        """
        Multimodal visual analysis using Gemini.
        """
        prompt = """Describe the scene in this image in ONE SHORT SENTENCE. 
Focus on: Actors (uniformed officials, citizens), Environment (Government office, road, checkpoint), and Key objects (Cash, Documents, Badges). 
Keep it neutral. Example: 'Uniformed officer standing on a road next to a vehicle.'
"""
        b64_image = base64.b64encode(image_bytes).decode('utf-8')
        
        contents = [{
            "parts": [
                {"text": prompt},
                {
                    "inlineData": {
                        "mimeType": mime_type,
                        "data": b64_image
                    }
                }
            ]
        }]
        
        result, retry_after = await cls._call_gemini(contents, model=cls.VISION_MODEL, timeout=timeout)
        
        if result:
            return str(result).strip(), None
        return None, retry_after

    @classmethod
    async def generate_pro_summary(cls, chat_history: List[Dict[str, str]], timeout: Optional[float] = None) -> Tuple[Optional[str], Optional[int]]:
        conversation_text = "\n".join([f"{msg['role'].upper()}: {msg['content']}" for msg in chat_history])
        contents = [{
            "parts": [{
                "text": (
                    "Write a professional intelligence summary of this report in a SINGLE CONCISE PARAGRAPH. "
                    "Preserve details (dates, names, amounts). Anonymize the reporter. "
                    "No fluff. Just the facts. Start directly with the summary content.\n\n"
                    f"Log:\n{conversation_text}"
                )
            }]
        }]
        result, retry_after = await cls._call_gemini(contents, timeout=timeout)
        if not result:
            return None, retry_after
            
        summary = str(result).strip()
        prefixes_to_strip = ["Intelligence Summary:", "Summary:", "Report Summary:"]
        for prefix in prefixes_to_strip:
            if summary.startswith(prefix):
                summary = summary[len(prefix):].strip()
        
        return summary, retry_after

    @classmethod
    async def calculate_credibility_score(
        cls, 
        chat_history: List[Dict[str, str]], 
        evidence_metadata: List[EvidenceMetadata], 
        metadata: Dict[str, Any],
        timeout: Optional[float] = None
    ) -> Tuple[Optional[ScoringResult], Optional[int]]:
        
        conversation_text = "\n".join([f"{msg['role'].upper()}: {msg['content']}" for msg in chat_history])
        
        evidence_digest = "NO EVIDENCE PROVIDED"
        if evidence_metadata:
            digest_lines = []
            for ev in evidence_metadata:
                status = "VALID"
                if ev.is_empty_or_corrupt: status = "CORRUPT/EMPTY"
                elif ev.is_duplicate: status = "DUPLICATE"
                digest_lines.append(f"- File: {ev.file_name} ({ev.file_type}) [{status}]")
                if ev.ocr_text_snippet: digest_lines.append(f"  OCR: {ev.ocr_text_snippet}")
                if ev.object_labels: digest_lines.append(f"  Visual: {', '.join(ev.object_labels)}")
            evidence_digest = "\n".join(digest_lines)

        system_prompt = """You are Beacon Credibility Engine. Your task is to perform an EXTREMELY CRITICAL and SKEPTICAL assessment of a corruption report.

═══════════════════════════════════════════════════════════════════
⚠️  CRITICAL INSTRUCTION: DEFAULT TO LOW SCORES
═══════════════════════════════════════════════════════════════════
- START with the assumption that the report is NOT credible.
- Credibility must be EARNED through specific details and relevant evidence.
- DO NOT be generous. DO NOT give benefit of the doubt.
- A score of 60+ should be RARE and requires STRONG evidence + detailed narrative.
- Most reports with weak/no evidence should score 15-40%.

═══════════════════════════════════════════════════════════════════
SCORING CRITERIA (0-100 Total = Sum of Subscores)
═══════════════════════════════════════════════════════════════════

1. NARRATIVE CONSISTENCY (0-40 points):
   ┌─────────────────────────────────────────────────────────────┐
   │ Score 0-10:  Vague, missing WHO/WHAT/WHERE/WHEN             │
   │ Score 11-20: Some details but lacks specifics               │
   │ Score 21-30: Reasonable detail, minor gaps                  │
   │ Score 31-40: Highly detailed, specific, logical             │
   └─────────────────────────────────────────────────────────────┘
   - If user didn't provide specific names, dates, locations → MAX 15 points
   - If story is just "someone took a bribe" with no specifics → 5-10 points
   - Contradictions or changes in story → deduct heavily

2. EVIDENCE STRENGTH (0-40 points):
   ┌─────────────────────────────────────────────────────────────┐
   │ Score 0:     NO evidence OR completely UNRELATED evidence   │
   │ Score 1-10:  Evidence is blurry/corrupt/empty/generic       │
   │ Score 11-20: Evidence exists but weak relevance to claims   │
   │ Score 21-30: Evidence partially supports specific claims    │
   │ Score 31-40: Strong, clear evidence directly proving claims │
   └─────────────────────────────────────────────────────────────┘
   - NO EVIDENCE PROVIDED = AUTOMATIC 0 POINTS
   - UNRELATED EVIDENCE (cat photo for bribery case) = AUTOMATIC 0 POINTS
   - Generic/random images = 0-5 points max
   - Blurry or corrupt files = 0-5 points
   - Text in image must be relevant to the claim for OCR credit

3. BEHAVIORAL RELIABILITY (0-20 points):
   ┌─────────────────────────────────────────────────────────────┐
   │ Score 0-5:   Evasive, contradictory, or uncooperative       │
   │ Score 6-10:  Minimal engagement or unclear responses        │
   │ Score 11-15: Reasonable cooperation with some gaps          │
   │ Score 16-20: Fully cooperative, consistent throughout       │
   └─────────────────────────────────────────────────────────────┘

═══════════════════════════════════════════════════════════════════
EXAMPLE LOW-SCORE SCENARIOS (These should score LOW!)
═══════════════════════════════════════════════════════════════════
• "I saw corruption" + no details + no evidence = 10-15%
• Vague story + random unrelated photo = 15-25%
• Some details + no evidence = 20-35%
• Good story + blurry/corrupt evidence = 25-40%
• Good story + evidence that doesn't match narrative = 20-35%

═══════════════════════════════════════════════════════════════════
EVIDENCE ANALYSIS RULES
═══════════════════════════════════════════════════════════════════
- 'sharp_high_clarity_image' alone is NOT enough - it must be RELEVANT
- 'signal: general_scene_or_object' = assess if scene matches the claimed corruption
- If OCR text is present, verify it relates to the claim (dates, names, amounts)
- Audio transcripts must contain relevant dialogue/admissions
- MISMATCH = 0 evidence score (e.g., traffic bribe report + grocery receipt)

═══════════════════════════════════════════════════════════════════
FINAL SCORE RANGES (0-100) & CONFIDENCE LEVEL
═══════════════════════════════════════════════════════════════════
┌────────────────┬─────────────────┬─────────────────────────────────┐
│ Score Range    │ Confidence      │ Description                     │
├────────────────┼─────────────────┼─────────────────────────────────┤
│  0 - 33        │ LOW             │ Weak/vague report, no evidence  │
│ 34 - 66        │ MEDIUM          │ Some credibility, partial proof │
│ 67 - 100       │ HIGH            │ Strong details + solid evidence │
└────────────────┴─────────────────┴─────────────────────────────────┘

CRITICAL: 
- You MUST use the 'Visual: ...' descriptions in the Evidence Metadata.
- If the "Visual" description matches the "Narrative" (e.g., Narrative says 'officer', Visual says 'man in uniform'), GIVE HIGH EVIDENCE POINTS (20-30).
- If the "Visual" description contradicts the Narrative, GIVE 0 POINTS.


SET confidence_level based on the total credibility_score:
- credibility_score 0-33  → confidence_level = "Low"
- credibility_score 34-66 → confidence_level = "Medium"  
- credibility_score 67-100 → confidence_level = "High"
"""
        contents = [{
            "parts": [{"text": f"Case Narrative:\n{conversation_text}\n\nEvidence Metadata & Extraction:\n{evidence_digest}"}]
        }]
        
        return await cls._call_gemini(contents, ScoringResult, timeout=timeout, system_instruction=system_prompt)

    @classmethod
    async def safe_chat(cls, messages: List[Dict[str, Any]], model: str = None, timeout: float = 10.0) -> Tuple[Optional[str], Optional[int]]:
        """Unified chat helper - converts OpenAI-style messages to Gemini format."""
        # Extract system message if present
        system_instruction = None
        user_messages = []
        
        for msg in messages:
            role = msg.get("role", "user").lower()
            content = msg.get("content", "")
            
            if role == "system":
                system_instruction = content
            else:
                # Convert to Gemini format
                # Map 'assistant' to 'model' for Gemini
                gemini_role = "model" if role == "assistant" else "user"
                user_messages.append({
                    "role": gemini_role,
                    "parts": [{"text": content}]
                })
        
        # Ensure we have valid contents
        if not user_messages:
            return None, None
        
        return await cls._call_gemini(
            user_messages, 
            model=model or cls.TEXT_MODEL, 
            timeout=timeout,
            system_instruction=system_instruction
        )

    @classmethod
    async def transcribe_audio(cls, audio_bytes: bytes, mime_type: str, timeout: Optional[float] = None) -> Optional[str]:
        """
        Transcribe audio using Gemini's multimodal capabilities.
        Gemini 2.5 Flash supports audio input natively.
        """
        if not settings.GEMINI_API_KEY:
            logger.warning("gemini_api_key_missing")
            return None

        b64_audio = base64.b64encode(audio_bytes).decode('utf-8')
        
        contents = [{
            "parts": [
                {"text": "Transcribe the following audio. Output ONLY the transcribed text, nothing else."},
                {
                    "inlineData": {
                        "mimeType": mime_type,
                        "data": b64_audio
                    }
                }
            ]
        }]

        result, _ = await cls._call_gemini(contents, model=cls.VISION_MODEL, timeout=timeout or 60.0)
        return str(result).strip() if result else None


# Backward compatibility alias
GroqService = GeminiService
