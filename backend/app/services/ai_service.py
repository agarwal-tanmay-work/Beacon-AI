import httpx
import json
import structlog
from typing import Optional, Dict, Any, Type, TypeVar, List, Tuple
from pydantic import BaseModel
from app.core.config import settings
from app.schemas.ai import AIAnalysisResult, EvidenceMetadata, ScoringResult
import base64

logger = structlog.get_logger()
T = TypeVar("T", bound=BaseModel)

class GroqService:
    """
    Service for interacting with Groq Cloud API (Llama 3 models).
    Layer 2: Logic & Reasoning Engine.
    """
    
    BASE_URL = "https://api.groq.com/openai/v1/chat/completions"
    TIMEOUT = 20.0 # Increased from 10.0 for better baseline resilience
    
    # Updated Models (Jan 2026)
    # Downgraded for speed and rate-limit resilience
    TEXT_MODEL = "llama-3.1-8b-instant"
    VISION_MODEL = "llama-3.2-11b-vision-preview" # Enabling cloud vision for evidence analysis

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
    async def _call_groq(cls, messages: List[Dict[str, Any]], schema_class: Optional[Type[T]] = None, model: str = TEXT_MODEL, timeout: Optional[float] = None) -> Tuple[Optional[T | str], Optional[int]]:
        """
        Returns: (result, retry_after_seconds)
        """
        if not settings.GROQ_API_KEY:
            logger.warning("groq_api_key_missing")
            return None, None

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {settings.GROQ_API_KEY}"
        }
        
        # JSON Schema Enforcement
        if schema_class:
            system_instruction = f"You must output STRICT VALID JSON matching this schema: {schema_class.model_json_schema()}"
            messages.insert(0, {"role": "system", "content": system_instruction})
            
        payload = {
            "model": model,
            "messages": messages,
            "temperature": 0.1, # Lower temperature for strict reasoning
            "max_tokens": 2048,
        }
        
        if schema_class:
            payload["response_format"] = {"type": "json_object"}

        effective_timeout = timeout if timeout is not None else cls.TIMEOUT

        client = await cls.get_client()
        try:
            response = await client.post(
                    cls.BASE_URL, 
                    headers=headers, 
                    json=payload, 
                    timeout=effective_timeout
                )
                
            if response.status_code == 429:
                retry_after = response.headers.get("Retry-After")
                wait_seconds = int(retry_after) if retry_after and retry_after.isdigit() else 1
                logger.error("groq_rate_limit_hit", status=429, retry_after=wait_seconds)
                return None, wait_seconds
                
            if response.status_code != 200:
                logger.error("groq_api_error", status=response.status_code, body=response.text[:500])
                return None, None
                
            data = response.json()
            content = data["choices"][0]["message"]["content"]
            
            if schema_class:
                try:
                    return schema_class.model_validate_json(content), None
                except Exception as e:
                    logger.error("groq_parse_error", error=str(e), content=content)
                    return None, None
                    
            return content, None

        except Exception as e:
            logger.error("groq_request_failed", error=str(e))
            return None, None

    @classmethod
    async def analyze_report(cls, report_text: str) -> Optional[AIAnalysisResult]:
        messages = [{
            "role": "user", 
            "content": f"Analyze this report. Extract entities, language, and corruption type.\n\nReport: {report_text}"
        }]
        result, _ = await cls._call_groq(messages, AIAnalysisResult)
        return result

    @classmethod
    async def translate_to_english(cls, text: str) -> str:
        messages = [{
            "role": "user",
            "content": f"Translate to English (return original if already English): {text}"
        }]
        result, _ = await cls._call_groq(messages)
        return str(result) if result else text

    @classmethod
    async def analyze_evidence(cls, file_bytes: bytes, mime_type: str) -> Dict[str, Any]:
        # Legacy single-file analysis
        b64_image = base64.b64encode(file_bytes).decode('utf-8')
        image_url = f"data:{mime_type};base64,{b64_image}"
        prompt = "Analyze this image. Describe visible text and objects."
        messages = [{
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": image_url}}
            ]
        }]
        result_text, _ = await cls._call_groq(messages, model=cls.VISION_MODEL)
        return {"analysis": result_text if result_text else "Visual analysis unavailable (Rate Limited)"}

    @classmethod
    async def perform_forensic_ocr_analysis(cls, ocr_text: str, narrative_summary: str, timeout: Optional[float] = None) -> Tuple[Optional[Any], Optional[int]]:
        from app.schemas.ai import ForensicOCRAnalysis
        
        system_prompt = """You are a forensic OCR text analysis module within Beacon Credibility Engine.
You DO NOT perform OCR. OCR has already been executed using Tesseract.
You ONLY analyze the extracted text provided to you.

Your task is to:
- Assess the quality and usefulness of the OCR output
- Identify objective, verifiable signals
- Detect relevance to the user’s narrative
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
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"--- USER NARRATIVE SUMMARY ---\n{narrative_summary}\n\n--- OCR EXTRACTED TEXT ---\n{ocr_text}"}
        ]
        return await cls._call_groq(messages, ForensicOCRAnalysis, timeout=timeout)

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
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"--- USER NARRATIVE SUMMARY ---\n{narrative_summary}\n\n{metadata_str}\n--- TRANSCRIPTION TEXT ---\n{transcript_text}"}
        ]
        return await cls._call_groq(messages, ForensicAudioAnalysis, timeout=timeout)

    @classmethod
    async def perform_forensic_visual_analysis(cls, image_bytes: bytes, mime_type: str, timeout: Optional[float] = None) -> Tuple[Optional[str], Optional[int]]:
        if cls.VISION_MODEL == "none":
            return None, None

        b64_image = base64.b64encode(image_bytes).decode('utf-8')
        image_url = f"data:{mime_type};base64,{b64_image}"
        
        prompt = """Describe the scene in this image in ONE SHORT SENTENCE. 
Focus on: Actors, Environment, Key objects. 
Keep it neutral. Example: 'Uniformed officer standing on a road next to a vehicle.'
"""
        messages = [{
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": image_url}}
            ]
        }]
        
        result, retry_after = await cls._call_groq(messages, model=cls.VISION_MODEL, timeout=timeout)
        return str(result).strip() if result else None, retry_after

    @classmethod
    async def generate_pro_summary(cls, chat_history: List[Dict[str, str]], timeout: Optional[float] = None) -> Tuple[Optional[str], Optional[int]]:
        conversation_text = "\n".join([f"{msg['role'].upper()}: {msg['content']}" for msg in chat_history])
        messages = [{
            "role": "user",
            "content": (
                "Write a professional intelligence summary of this report in a SINGLE CONCISE PARAGRAPH. "
                "Preserve details (dates, names, amounts). Anonymize the reporter. "
                "No fluff. Just the facts. Start directly with the summary content.\n\n"
                f"Log:\n{conversation_text}"
            )
        }]
        result, retry_after = await cls._call_groq(messages, timeout=timeout)
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
        messages = [{"role": "system", "content": system_prompt}, {"role": "user", "content": f"Case Narrative:\n{conversation_text}\n\nEvidence Metadata & Extraction:\n{evidence_digest}"}]
        
        return await cls._call_groq(messages, ScoringResult, timeout=timeout)

    @classmethod
    async def safe_chat(cls, messages: List[Dict[str, Any]], model: str = TEXT_MODEL, timeout: float = 10.0) -> Tuple[Optional[str], Optional[int]]:
        """Unified chat helper."""
        return await cls._call_groq(messages, model=model, timeout=timeout)
