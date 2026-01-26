import os
import json
import httpx
import re
import secrets
import asyncio
from typing import Tuple, Optional
from app.core.config import settings

SYSTEM_PROMPT = """You are Beacon AI — a calm, trustworthy, and respectful assistant helping citizens/employees report corruption/complaints safely and anonymously.

────────────────────────────────
🧠 CORE IDENTITY & PERSONA
────────────────────────────────

You speak like a calm, empathetic, and reassuring human who wants to help.
Your tone is Compassionate, Patient, Clear, and Non-judgmental.

You NEVER sound like a machine.
Keep responses natural and conversational. Be concise but do NOT sacrifice empathy.
Always acknowledge the user's distress or difficulty briefly before asking the next question.

────────────────────────────────
🎯 YOUR OBJECTIVE
────────────────────────────────

Collect details of a corruption/complaint incident conversationally. You must gather:
1. WHAT happened (The event)
2. WHERE (City, State, specific Building/Office, Landmark)
3. WHEN (Date AND Time - both required)
4. WHO (Names or Roles of officials involved)
5. EVIDENCE (Acknowledge if uploaded or ask if exists)
6. OPTIONAL CONTACT INFO (Explicitly ask if they want to provide it)
7. MORE INCIDENT DETAILS (Ask if they would like to provide any more incident details)
8. OTHER CONCERNS (Ask if there's anything else)

────────────────────────────────
🧭 CONVERSATION FLOW (STRICT RULES)
────────────────────────────────

- **ONE QUESTION AT A TIME**: STRICTLY ask only ONE question per turn. Never combine questions. Wait for the user's answer before proceeding.
- **DATE/TIME**: 
  - **STRICTLY REQUIRED**: You MUST obtain both a DATE and a TIME.
  - If user provides Date only, ACKNOWLEDGE it and ASK for the Time.
- **OPTIONAL CONTACT**: Ask EXACTLY: "Would you like to provide any contact details so we can follow up with you? This is **COMPLETELY OPTIONAL**. You may say 'no' or 'skip' to remain anonymous." (Ensure 'COMPLETELY OPTIONAL' is Bold and Uppercase).
- **MORE DETAILS**: After the contact info prompt (regardless of the answer), ask: "Would you like to provide any more incident details?"
- **FINALIZATION**: 
  - ONLY if user says "No" to "Any more incident details?" (or anything else), your NEXT response MUST be the final Case ID message.
  - Do NOT summarize facts first.

────────────────────────────────
🧾 FINALIZATION MESSAGE
────────────────────────────────

When finished (user says "no" to anything else), say EXACTLY this:

"Thank you for your courage in reporting this.

Your Case ID is: CASE_ID_PLACEHOLDER
Your Secret Key is: SECRET_KEY_PLACEHOLDER

**IMPORTANT**: Please save both of these safely to track your case status. We will investigate and take appropriate action. You've done the right thing by speaking up." (Strictly use ONLY these placeholders: CASE_ID_PLACEHOLDER and SECRET_KEY_PLACEHOLDER. DO NOT provide examples like CASE_ID_1234 or SECRET_KEY_5678).

────────────────────────────────
🧩 STRUCTURED DATA EXTRACTION (INTERNAL)
────────────────────────────────

At the VERY END of every response, include a JSON block with the extracted data.
Format:
```json
{
  "what": "",
  "where": "",
  "when": "",
  "who": "",
  "evidence": "",
  "contact_info": "",
  "other_details": ""
}
```
"""

class LLMAgent:
    """Groq-powered LLM Agent."""
    
    # Centralized in GroqService now, keeping for backward compatibility if needed locally
    GROQ_MODEL = "llama-3.1-8b-instant"
    
    @staticmethod
    async def chat(conversation_history: list, current_state: dict = None) -> Tuple[str, Optional[dict]]:
        print(f"[LLM_AGENT] chat() called with {len(conversation_history)} messages", flush=True)
        api_key = settings.GROQ_API_KEY
        if not api_key:
            print(f"[LLM_AGENT] No API key found, using mock", flush=True)
            return await LLMAgent._mock_chat(conversation_history, current_state)

        # 1. CLEAN HISTORY & STATE
        state = current_state.copy() if current_state else {}
        summary_parts = []
        track_fields = ["what", "where", "when", "who", "evidence", "contact_info", "other_details"]
        
        for k in track_fields:
            val = state.get(k)
            if val and str(val).lower() not in ["...", "", "none", "unknown", "null"]:
                summary_parts.append(f"- {k.upper()}: {val}")
        
        summary_text = "\n".join(summary_parts) if summary_parts else "No information yet."

        # 2. CONSTRUCT PROMPT
        full_system_prompt = f"{SYSTEM_PROMPT}\n\n### [CONFIRMED FACTS] ###\n{summary_text}\n##########################"
        
        messages = [{"role": "system", "content": full_system_prompt}]
        recent_history = conversation_history[-15:] if len(conversation_history) > 15 else conversation_history
        for msg in recent_history:
             messages.append({"role": msg["role"].lower(), "content": msg["content"]})
            
        # 3. API CALL (UNIFIED STRATEGY)
        from app.services.ai_service import GroqService
        try:
            # GroqService.safe_chat handles timeouts and 429 logging internally
            # It returns (content, retry_after)
            text_response, retry_after = await GroqService.safe_chat(messages, model=LLMAgent.GROQ_MODEL, timeout=10.0)
            
            if text_response:
                # Extract fresh JSON
                fresh_extracted = LLMAgent._extract_report(text_response) or {}
                
                # Merge with State
                final_report_to_save = state.copy()
                for k in track_fields:
                    v = fresh_extracted.get(k)
                    val = str(v).strip() if v is not None else ""
                    if val and val.lower() not in ["", "none", "unknown", "null", "..."]:
                        old_val = str(state.get(k) or "").lower()
                        if val.lower() != old_val:
                            final_report_to_save[k] = val
                
                clean_response = LLMAgent._clean_response(text_response)
                
                # Placeholder Consistency Fix
                clean_response = re.sub(r"case_id_placeholder", "CASE_ID_PLACEHOLDER", clean_response, flags=re.I)
                clean_response = re.sub(r"secret_key_placeholder", "SECRET_KEY_PLACEHOLDER", clean_response, flags=re.I)
                
                # Fix for hallucinations
                if "case id" in clean_response.lower() and "secret key" in clean_response.lower():
                    if "CASE_ID_PLACEHOLDER" not in clean_response:
                        clean_response = re.sub(r"BCN-\d+", "CASE_ID_PLACEHOLDER", clean_response)
                        if "CASE_ID_PLACEHOLDER" not in clean_response:
                            clean_response = re.sub(r"(Case ID is\s+)([A-Z0-9-]+)", r"\1CASE_ID_PLACEHOLDER", clean_response, flags=re.I)
                    
                    if "SECRET_KEY_PLACEHOLDER" not in clean_response:
                        clean_response = re.sub(r"(Secret Key is\s+)([A-Z0-9-]+)", r"\1SECRET_KEY_PLACEHOLDER", clean_response, flags=re.I)

                return clean_response, final_report_to_save

            elif retry_after:
                print(f"[LLM_AGENT] Rate limit hit. Retry-After: {retry_after}s", flush=True)
                return f"I'm currently experiencing high traffic. Please try sending your message again in a few seconds.", state

            else:
                print(f"[LLM_AGENT] Groq service returned no response and no retry hint.", flush=True)
                return await LLMAgent._mock_chat(conversation_history, current_state)

        except Exception as e:
            print(f"[LLM_AGENT] Unexpected error during chat: {e}", flush=True)
            import traceback
            traceback.print_exc()
            return await LLMAgent._mock_chat(conversation_history, current_state)

    @staticmethod
    async def analyze_image_fast(file_path: str) -> str:
        """Fast visual context extraction."""
        print(f"[LLM_AGENT] analyze_image_fast: {file_path}", flush=True)
        try:
            from app.services.storage_service import StorageService
            from app.services.ai_service import GroqService

            content = None
            if file_path.startswith("supastorage://"):
                parts = file_path.replace("supastorage://", "").split("/", 1)
                content = StorageService.download_file(parts[0], parts[1])
            else:
                if os.path.exists(file_path):
                    with open(file_path, "rb") as f:
                        content = f.read()

            if content:
                from app.services.ai_service import GroqService
                if GroqService.VISION_MODEL == "none":
                    # Fallback to a neutral acknowledgement if vision is disabled
                    # This tells the user we've received it and are processing it with local tools (OpenCV/OCR)
                    return "Image received. I've noted the visual evidence and will include it in the final report analysis."
                
                desc, _ = await GroqService.perform_forensic_visual_analysis(content, "image/jpeg", timeout=10.0)
                return desc or "An image was uploaded but I couldn't process it clearly."
            return "An image file was detected."
        except Exception as e:
            print(f"[LLM_AGENT] analyze_image_fast error: {e}", flush=True)
            return "An image was uploaded."

    @staticmethod
    async def analyze_audio_fast(file_path: str) -> str:
        """Fast audio/video context placeholder (Whisper is too slow for real-time chat usually)."""
        # We just acknowledge the file type for now to keep chat snappy
        ext = file_path.split(".")[-1].lower()
        if ext in ["mp3", "wav", "m4a", "aac"]:
            return "An audio recording was uploaded. I'll include it in the report analysis."
        if ext in ["mp4", "mov", "avi"]:
            return "A video file was uploaded. I'll include it in the report analysis."
        return "A media file was uploaded."

    @staticmethod
    async def _mock_chat(conversation_history: list, current_state: dict = None) -> Tuple[str, Optional[dict]]:
        state = current_state.copy() if current_state else {}
        return "I'm having a bit of trouble connecting to my brain. Could you please repeat that or try again in a moment?", state

    @staticmethod
    def _clean_response(text: str) -> str:
        # 1. Remove Markdown Code Blocks
        text = re.sub(r'```json\s*\{[\s\S]*?\}\s*```', '', text, flags=re.DOTALL)
        text = re.sub(r'```\s*\{[\s\S]*?\}\s*```', '', text, flags=re.DOTALL)
        
        # 2. Remove Thought Blocks
        text = re.sub(r'<thought>[\s\S]*?</thought>', '', text, flags=re.DOTALL)
        
        # 3. Cleanup Confirmed Facts / Summary Leaks
        text = re.sub(r'###\s*\[CONFIRMED FACTS\]\s*###[\s\S]*?##########################', '', text, flags=re.DOTALL)
        text = re.sub(r'(Confirmed Facts|Summary of Information):.*', '', text, flags=re.DOTALL | re.IGNORECASE)

        # 4. AGGRESSIVE JSON STRIPPING
        text = re.sub(r'\s*\{[\s\S]*?"what"[\s\S]*?\}\s*$', '', text, flags=re.DOTALL|re.IGNORECASE) 

        # 5. Final whitespace cleanup
        cleaned = re.sub(r'\n{3,}', '\n\n', text).strip()
        if not cleaned:
            return "I've noted that. What else can you tell me?"
        return cleaned

    @staticmethod
    def _extract_report(text: str) -> Optional[dict]:
        matches = re.findall(r'```json\s*(\{[\s\S]*?\})\s*```', text)
        if not matches:
            matches = re.findall(r'(\{[\s\S]*?"what"[\s\S]*?\})', text)
            
        if matches:
            try:
                json_str = matches[-1].strip()
                last_brace = json_str.rfind('}')
                if last_brace != -1: json_str = json_str[:last_brace+1]
                return json.loads(json_str)
            except: pass
        return None

    @staticmethod
    async def rewrite_update(raw_text: str) -> str:
        from app.services.ai_service import GroqService
        result, _ = await GroqService.safe_chat(
            messages=[
                {"role": "system", "content": "Rewrite the following Admin update to be neutral, concise, and professional for public display. Do not add any conversational filler. Output ONLY the rewritten update."},
                {"role": "user", "content": f"Update to rewrite:\n\n{raw_text}"}
            ],
            timeout=10.0
        )
        return result.strip() if result else raw_text
