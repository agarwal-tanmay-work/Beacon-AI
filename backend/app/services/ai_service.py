import httpx
import json
import structlog
from typing import Optional, Dict, Any, Type, TypeVar, List
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
    TIMEOUT = 60.0 
    TEXT_MODEL = "llama-3.1-8b-instant"
    VISION_MODEL = "meta-llama/llama-4-scout-17b-16e-instruct"

    @classmethod
    async def _call_groq(cls, messages: List[Dict[str, Any]], schema_class: Optional[Type[T]] = None, model: str = TEXT_MODEL) -> Optional[T | str]:
        if not settings.GROQ_API_KEY:
            logger.warning("groq_api_key_missing")
            return None

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
                return None

    @classmethod
    async def analyze_report(cls, report_text: str) -> Optional[AIAnalysisResult]:
        messages = [{
            "role": "user", 
            "content": f"Analyze this report. Extract entities, language, and corruption type.\n\nReport: {report_text}"
        }]
        return await cls._call_groq(messages, AIAnalysisResult)

    @classmethod
    async def translate_to_english(cls, text: str) -> str:
        messages = [{
            "role": "user",
            "content": f"Translate to English (return original if already English): {text}"
        }]
        result = await cls._call_groq(messages)
        return str(result) if result else text

    @classmethod
    async def analyze_evidence(cls, file_bytes: bytes, mime_type: str) -> Dict[str, Any]:
        # Legacy single-file analysis if needed, but Layer 1 is preferred now.
        # Keeping for backward compatibility or direct calls.
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
        result_text = await cls._call_groq(messages, model=cls.VISION_MODEL)
        result_text = await cls._call_groq(messages, model=cls.VISION_MODEL)
        return {"analysis": result_text if result_text else "Analysis failed"}

    @classmethod
    async def perform_forensic_ocr_analysis(cls, ocr_text: str, narrative_summary: str) -> Optional[Any]: # Returns ForensicOCRAnalysis schema
        from app.schemas.ai import ForensicOCRAnalysis
        
        system_prompt = """You are a forensic OCR text analysis module within Beacon Credibility Engine.

You DO NOT perform OCR.
OCR has already been executed using Tesseract.
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
- Do NOT correct OCR errors unless they are obvious formatting issues
- Treat low-quality or noisy OCR neutrally, not negatively

--------------------------------------------------

ANALYZE FOR THE FOLLOWING OBJECTIVE SIGNALS:

1. TEXT PRESENCE
- Is meaningful text present or mostly noise?

2. FACTUAL ELEMENTS
Identify whether the OCR text contains:
- Dates
- Monetary amounts
- Names (persons or organizations)
- Locations
- Official indicators (letterheads, stamps, IDs, reference numbers)

3. RELEVANCE ALIGNMENT
- Do any extracted elements align with the user’s claimed facts?
- Alignment can be partial or indirect

4. LIMITATIONS
- Note missing, unclear, or unreadable portions
- Note OCR ambiguity without speculation

--------------------------------------------------

FINAL SAFETY RULE:
This analysis reflects OCR text characteristics only.
It does not verify authenticity, truth, or legality of the content.
"""
        messages = [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": (
                    f"--- USER NARRATIVE SUMMARY ---\n{narrative_summary}\n\n"
                    f"--- OCR EXTRACTED TEXT ---\n{ocr_text}"
                )
            }
        ]
        
        return await cls._call_groq(messages, ForensicOCRAnalysis)

    @classmethod
    async def perform_forensic_audio_analysis(cls, transcript_text: str, narrative_summary: str, audio_metadata: dict = None) -> Optional[Any]:
        from app.schemas.ai import ForensicAudioAnalysis
        
        metadata_str = ""
        if audio_metadata:
            metadata_str = f"""
TRANSCRIPTION_METADATA:
- Audio clarity: {audio_metadata.get('clarity', 'unknown')}
- Multiple speakers: {audio_metadata.get('multiple_speakers', 'unclear')}
- Duration: {audio_metadata.get('duration_seconds', 'unknown')} seconds
- Language: {audio_metadata.get('language', 'unknown')}
"""
        
        system_prompt = """You are a forensic audio/video transcription analysis module within the Beacon Credibility Engine.

You DO NOT process media files.
You DO NOT perform audio decoding or transcription.
Audio/video preprocessing was completed using FFmpeg, and transcription was produced by an external speech-to-text system.

Your role is ONLY to analyze the resulting transcription and metadata objectively.

--------------------------------------------------

STRICT ANALYSIS RULES:

- Do NOT assume the speaker's intent, identity, or role
- Do NOT infer illegality, corruption, or wrongdoing
- Do NOT "clean up" speech beyond basic readability
- Treat unclear or partial transcription neutrally
- Absence of relevant speech is NOT evidence of falsehood

--------------------------------------------------

ANALYZE FOR THE FOLLOWING OBJECTIVE SIGNALS:

1. TRANSCRIPTION USABILITY
- Is meaningful speech present or mostly noise?
- Is the audio sufficiently intelligible to extract facts?

2. FACTUAL ELEMENTS IN SPEECH
Identify whether the transcription includes:
- Dates or time references
- Monetary amounts
- Names (people or organizations)
- Locations
- References to documents, payments, or official actions
(Note: Listing presence only, not interpretation.)

3. NARRATIVE ALIGNMENT
- Do any spoken elements align with the user's claimed facts?
- Alignment may be partial, indirect, or contextual

4. LIMITATIONS & AMBIGUITIES
- Overlapping speakers
- Poor audio quality
- Missing segments
- Language uncertainty

--------------------------------------------------

FINAL SAFETY STATEMENT:
This analysis reflects transcription characteristics only.
It does not verify speaker identity, authenticity, intent, legality, or factual truth.
"""
        messages = [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": (
                    f"--- USER NARRATIVE SUMMARY ---\n{narrative_summary}\n\n"
                    f"{metadata_str}\n"
                    f"--- TRANSCRIPTION TEXT ---\n{transcript_text}"
                )
            }
        ]
        
        return await cls._call_groq(messages, ForensicAudioAnalysis)

    @classmethod
    async def perform_forensic_visual_analysis(cls, image_bytes: bytes, mime_type: str) -> Optional[str]:
        """
        Qualitative scene description for Layer 2.
        NEUTRAL and OBJECTIVE.
        """
        b64_image = base64.b64encode(image_bytes).decode('utf-8')
        image_url = f"data:{mime_type};base64,{b64_image}"
        
        prompt = """Describe the scene in this image in ONE SHORT SENTENCE. 
Focus on:
1. Actors (e.g., uniformed personnel, civilian, office clerk, shopkeeper)
2. Environment (e.g., road, office, shop, indoors)
3. Key objects (e.g., documents, money, vehicle)

Keep it neutral. Example: 'Uniformed officer standing on a road next to a vehicle.'
"""
        messages = [{
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": image_url}}
            ]
        }]
        
        result = await cls._call_groq(messages, model=cls.VISION_MODEL)
        return str(result).strip() if result else None

    @classmethod
    async def generate_pro_summary(cls, chat_history: List[Dict[str, str]]) -> str:
        conversation_text = "\n".join([f"{msg['role'].upper()}: {msg['content']}" for msg in chat_history])
        messages = [{
            "role": "user",
            "content": (
                "Write a professional intelligence summary of this report. "
                "Preserve details (dates, names, amounts). Anonymize the reporter. "
                "No fluff. Just the facts. "
                "CRITICAL: Do NOT include a title, header, or prefix like 'Intelligence Summary:'. "
                "Start directly with the summary content.\n\n"
                f"Log:\n{conversation_text}"
            )
        }]
        result = await cls._call_groq(messages)
        if not result:
            return "No summary generated."
            
        summary = str(result).strip()
        # Cleanup: Forcefully remove common prefixes if the LLM ignores instructions
        prefixes_to_strip = ["Intelligence Summary:", "Summary:", "Report Summary:"]
        for prefix in prefixes_to_strip:
            if summary.startswith(prefix):
                summary = summary[len(prefix):].strip()
        
        return summary

    @classmethod
    async def calculate_credibility_score(
        cls, 
        chat_history: List[Dict[str, str]], 
        evidence_metadata: List[EvidenceMetadata], 
        metadata: Dict[str, Any]
    ) -> Optional[ScoringResult]:
        
        conversation_text = "\n".join([f"{msg['role'].upper()}: {msg['content']}" for msg in chat_history])
        
        # Build Layer 1 Deterministic Summary for the LLM
        evidence_digest = "NO EVIDENCE PROVIDED"
        if evidence_metadata:
            digest_lines = []
            for ev in evidence_metadata:
                status = "VALID"
                if ev.is_empty_or_corrupt: status = "CORRUPT/EMPTY"
                elif ev.is_duplicate: status = "DUPLICATE"
                
                digest_lines.append(f"- File: {ev.file_name} ({ev.file_type}) [{status}]")
                digest_lines.append(f"  OCR Text: {ev.ocr_text_snippet if ev.ocr_text_snippet else '[NO TEXT DETECTED]'}")
                digest_lines.append(f"  Visual Signals: {', '.join(ev.object_labels) if ev.object_labels else '[OFFICE/CURRENCY SIGNALS NOT FOUND]'}")
                if ev.audio_transcript_snippet:
                    digest_lines.append(f"  Audio Transcript: {ev.audio_transcript_snippet}")
            evidence_digest = "\n".join(digest_lines)

        system_prompt = """You are Beacon Credibility Engine.
You are a forensic consistency analyst assessing whether provided evidence meaningfully supports a corruption claim.

CORE PRINCIPLES:
1. Credibility != Truth. You assess coherence, not guilt.
2. Evidence validates narrative. If evidence is unrelated (e.g., ashtray photo for a bribe claim), it is a STRONG NEGATIVE SIGNAL.
3. Be skeptical of polished stories with unrelated attachments.

SCORING RUBRIC (Strictly Enforced):

1. NARRATIVE CREDIBILITY (0-40)
   - Evaluates: Internal consistency, specific details (dates, names, amounts), logical flow.
   - Penalize: Contradictions, vagueness, emotional instead of factual language.

2. EVIDENCE STRENGTH (0-40)
   - Evaluates: Relevance and alignment between Evidence Digest and the Narrative.
   - RELEVANCE CHECK: Does the visual signal or OCR directly correlate with the narrative?
   - ACTOR/ENVIRONMENT MATCH: If the narrative mentions a specific actor (e.g., Shopkeeper) but the Visual Context describes a different one (e.g., Police Officer), this is a CRITICAL MISMATCH. Score = 0-10.
   - REWARD: If the narrative mentions "cash" or "money" AND Visual Signals show "possible_currency_colors", Score = 25-35.
   - REWARD: If the narrative mentions a location/office AND Visual Signals show "possible_document_layout", Score = 20-30.
   - CRITICAL PENALTY: If the evidence is entirely unrelated (e.g. ashtray) or shows a role mismatch as noted above.
   - CRITICAL CONSTRAINT: If the provided Evidence Digest shows "[NO TEXT DETECTED]" for a document claim, and no visual signals match, Score < 10.

3. BEHAVIORAL RELIABILITY (0-20)
   - Evaluates: Stability, cooperation, natural timing.
   - Penalize: Evasiveness, robotic repetition.

TOTAL SCORE = Sum(Subscores). Max 100.
"""

        messages = [
            {"role": "system", "content": system_prompt},
            {
                "role": "user", 
                "content": (
                    "Evaluate this case.\n\n"
                    f"--- NARRATIVE ---\n{conversation_text}\n\n"
                    f"--- LAYER 1 EVIDENCE DIGEST (DETERMINISTIC) ---\n{evidence_digest}\n\n"
                    f"--- METADATA ---\n{json.dumps(metadata, default=str)}"
                )
            }
        ]
        
        return await cls._call_groq(messages, ScoringResult)
