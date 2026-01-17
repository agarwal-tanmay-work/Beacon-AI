import os
import json
import httpx
import re
import secrets
import asyncio
from typing import Tuple, Optional
from app.core.config import settings

SYSTEM_PROMPT = """You are Beacon AI — a calm, trustworthy, and respectful assistant helping citizens report corruption safely and anonymously.

────────────────────────────────
🧠 CORE IDENTITY & PERSONA
────────────────────────────────

You speak like a calm, attentive human who wants to understand clearly and help responsibly(You must follow this and the persona while asking every question to comfort the user!).

Your tone is:
- Calm
- Reassuring (without emotional exaggeration)
- Neutral and respectful
- Clear and direct
- Non-judgmental

You NEVER sound like:
- A form, a robot, or a machine.

Keep responses concise and natural (1–2 short sentences).

────────────────────────────────
🔐 TRUST & ANONYMITY
────────────────────────────────

- Sharing identity is NOT required.
- NEVER ask for name or personal contact details until the specific optional step.

────────────────────────────────
🎯 YOUR OBJECTIVE
────────────────────────────────

Collect details of a corruption incident conversationally. You must gather:
1. WHAT happened (The event)
2. WHERE (City, State, specific Building/Office, Landmark)
3. WHEN (Date AND Time - both required)
4. WHO (Names or Roles of officials involved)
5. EVIDENCE (Acknowledge if uploaded or ask if exists)
6. OPTIONAL CONTACT INFO (Explicitly ask if they want to provide it)
7. OTHER DETAILS (Ask if anything else remains)

────────────────────────────────
🧭 CONVERSATION FLOW (STRICT)
────────────────────────────────

- You must progress logically. Do NOT skip steps unless the user provides the info ahead of time.
- **GUARDRAILS (Staying on Track)**: If the user provides input that is completely unrelated to corruption reporting or asks off-topic questions (e.g., about weather, recipes, or general chat), acknowledge them briefly and politely pivot back to the report. For example: "I'm here specifically to help you report corruption safely. To continue with your report, could you tell me more about [next required field]?"
- **OPTIONAL CONTACT INFO**: You MUST ask: "Would you like to provide any contact details so we can follow up with you? This is **COMPLETELY OPTIONAL**. You may say 'no' or 'skip' to remain anonymous." (Use this EXACT bold/caps wording).
- If a user says "no" or "skip" to an optional step, respect it immediately and move to the next item.

────────────────────────────────
🧠 INTELLIGENCE & EXTRACTION
────────────────────────────────

- You are a highly intelligent entity extraction engine.
- If a user provides multiple details at once (e.g. "Gurugram, Haryana at the RTO office"), extract ALL (City: Gurugram, State: Haryana, Office: RTO).
- Do NOT re-ask for details already confirmed in the [CONFIRMED FACTS] block.
- **DATE/TIME**: If a user says "Yesterday at 3 PM", extract both. If they only give one, ask for the other.

────────────────────────────────
🧾 FINALIZATION BEHAVIOR
────────────────────────────────

Once you have gathered everything and the user confirms they have finished, say EXACTLY this:

"Thank you for your courage in reporting this. Your Case ID is CASE_ID_PLACEHOLDER. Your Secret Key is SECRET_KEY_PLACEHOLDER. Please save these details to track your case. We will investigate and take appropriate action. You've done the right thing by speaking up."

Do NOT add anything before or after this final message.
Do NOT hallucinate a Case ID like "BCN-123". You MUST use the placeholder `CASE_ID_PLACEHOLDER`.

────────────────────────────────
🧩 STRUCTURED DATA EXTRACTION (INTERNAL)
────────────────────────────────

At the VERY END of every response, include a JSON block with the extracted data. This persists the session.
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
    
    GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
    GROQ_MODEL = "llama-3.1-8b-instant"
    
    @staticmethod
    async def chat(conversation_history: list, current_state: dict = None) -> Tuple[str, Optional[dict]]:
        api_key = settings.GROQ_API_KEY
        if not api_key:
            return await LLMAgent._mock_chat(conversation_history, current_state)

        # 1. CLEAN HISTORY & STATE
        state = current_state.copy() if current_state else {}
        summary_parts = []
        # Define fields to track
        track_fields = ["what", "where", "when", "who", "evidence", "contact_info", "other_details"]
        
        for k in track_fields:
            val = state.get(k)
            if val and str(val).lower() not in ["...", "", "none", "unknown", "null"]:
                summary_parts.append(f"- {k.upper()}: {val}")
        
        summary_text = "\n".join(summary_parts) if summary_parts else "No information yet."

        # 2. CONSTRUCT PROMPT
        full_system_prompt = f"{SYSTEM_PROMPT}\n\n### [CONFIRMED FACTS] ###\n{summary_text}\n##########################"
        
        messages = [{"role": "system", "content": full_system_prompt}]
        # Provide enough context for extraction logic
        recent_history = conversation_history[-15:] if len(conversation_history) > 15 else conversation_history
        for msg in recent_history:
             messages.append({"role": msg["role"].lower(), "content": msg["content"]})
            
        # 3. PREPARE PAYLOAD
        payload = {
            "model": LLMAgent.GROQ_MODEL,
            "messages": messages,
            "temperature": 0.1, 
            "max_tokens": 1024
        }
        
        headers = {
            "Authorization": f"Bearer {api_key.strip()}",
            "Content-Type": "application/json"
        }
        
        # 4. API CALL WITH RETRIES
        max_retries = 2
        for attempt in range(max_retries + 1):
            try:
                async with httpx.AsyncClient() as client:
                    response = await client.post(LLMAgent.GROQ_API_URL, json=payload, headers=headers, timeout=25.0)
                    
                    if response.status_code == 200:
                        data = response.json()
                        text_response = data["choices"][0]["message"]["content"]
                        
                        # Extract fresh JSON
                        fresh_extracted = LLMAgent._extract_report(text_response) or {}
                        
                        # Merge with State (Trust LLM's latest extraction if it's not empty)
                        final_report_to_save = state.copy()
                        for k in track_fields:
                            v = fresh_extracted.get(k)
                            val = str(v).strip() if v is not None else ""
                            if val and val.lower() not in ["", "none", "unknown", "null", "..."]:
                                # Update if different or currently empty
                                old_val = str(state.get(k) or "").lower()
                                if val.lower() != old_val:
                                    final_report_to_save[k] = val
                        
                        clean_response = LLMAgent._clean_response(text_response)
                        
                        # Placeholder Consistency Fix (Case-insensitive catch-all)
                        clean_response = re.sub(r"case_id_placeholder", "CASE_ID_PLACEHOLDER", clean_response, flags=re.I)
                        clean_response = re.sub(r"secret_key_placeholder", "SECRET_KEY_PLACEHOLDER", clean_response, flags=re.I)
                        
                        # Fix for hallucinations (BCN-XXXX or similar)
                        # If the AI hallucinated a case ID format, we try to force the placeholder back if it's the final message
                        if "case id" in clean_response.lower() and "secret key" in clean_response.lower():
                            if "CASE_ID_PLACEHOLDER" not in clean_response:
                                # Replace anything that looks like BCN-#### with the placeholder
                                clean_response = re.sub(r"BCN-\d+", "CASE_ID_PLACEHOLDER", clean_response)
                                # If still not there, it might be a different format. 
                                # We'll do a generic replacement if placeholders are missing in the final block.
                                if "CASE_ID_PLACEHOLDER" not in clean_response:
                                    # Very broad check: if it says "Case ID is [some value]", replace [some value]
                                    clean_response = re.sub(r"(Case ID is\s+)([A-Z0-9-]+)", r"\1CASE_ID_PLACEHOLDER", clean_response, flags=re.I)
                            
                            if "SECRET_KEY_PLACEHOLDER" not in clean_response:
                                clean_response = re.sub(r"(Secret Key is\s+)([A-Z0-9-]+)", r"\1SECRET_KEY_PLACEHOLDER", clean_response, flags=re.I)

                        return clean_response, final_report_to_save
                        
                    elif response.status_code == 429:
                        await asyncio.sleep(5)
                        continue
                    else:
                        break # Fallback to mock
                        
            except Exception as e:
                print(f"[LLM_AGENT] Attempt {attempt+1} failed: {e}")
                if attempt < max_retries: await asyncio.sleep(1)
        
        return await LLMAgent._mock_chat(conversation_history, current_state)

    @staticmethod
    async def _mock_chat(conversation_history: list, current_state: dict = None) -> Tuple[str, Optional[dict]]:
        state = current_state.copy() if current_state else {}
        return "I'm having a bit of trouble connecting to my brain. Could you please repeat that or try again in a moment?", state

    @staticmethod
    def _clean_response(text: str) -> str:
        # Remove JSON blocks
        text = re.sub(r'```json\s*\{[\s\S]*?\}\s*```', '', text, flags=re.DOTALL)
        # Remove thought blocks
        text = re.sub(r'<thought>[\s\S]*?</thought>', '', text, flags=re.DOTALL)
        # Cleanup confirmed facts leaks
        text = re.sub(r'###\s*\[CONFIRMED FACTS\]\s*###[\s\S]*?##########################', '', text, flags=re.DOTALL)
        
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
        UPDATE_SYSTEM_PROMPT = "Rewrite this NGO update to be neutral and concise for public display."
        api_key = settings.GROQ_API_KEY
        if not api_key: return raw_text
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    LLMAgent.GROQ_API_URL,
                    json={
                        "model": "llama-3.1-8b-instant",
                        "messages": [{"role": "system", "content": UPDATE_SYSTEM_PROMPT}, {"role": "user", "content": raw_text}],
                        "temperature": 0.1, "max_tokens": 150
                    },
                    headers={"Authorization": f"Bearer {api_key}"},
                    timeout=20.0
                )
                if response.status_code == 200:
                    return response.json()["choices"][0]["message"]["content"].strip()
        except: pass
        return raw_text

    @staticmethod
    async def analyze_image_fast(file_path: str, known_mime_type: str = None) -> str:
        return "Image attachment detected. Verification in progress."

    @staticmethod
    async def analyze_audio_fast(file_path: str) -> str:
        return "Audio attachment detected. Transcription in progress."
