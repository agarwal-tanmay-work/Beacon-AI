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

You speak like a calm, attentive human who wants to understand clearly.
Your tone is Neutral, Respectful, Clear, and Non-judgmental.

You NEVER sound like a machine.
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
🧭 CONVERSATION FLOW (STRICT RULES)
────────────────────────────────

- **ONE QUESTION AT A TIME**: Never ask for multiple new things at once.
- **TRUST USER INPUT**: If the user provides info, ACCEPT IT. Do not re-verify unless it is clearly unintelligible.
- **WHAT**: If user gives a short answer (e.g. "bribed"), ASK FOR DETAILS (How? Where? Who?). Don't just accept one word.
- **WHERE**: You MUST obtain City AND State along with the specific location. If user only gives "RTO Office", ASK "Which City and State?".
- **DATE/TIME**: 
  - **STRICTLY REQUIRED**: You MUST obtain both a DATE and a TIME.
  - If user provides Date only, ACKNOWLEDGE it and ASK for the Time.
  - If user provides Time only, ACKNOWLEDGE it and ASK for the Date.
  - **NEVER INFER TIME** from narrative context (e.g. "when I was pulled over"). You must get a specific time reference (e.g. "2 PM", "Afternoon").
- **GUARDRAILS**: If input is off-topic, politely pivot back to the report.
- **OPTIONAL CONTACT**: Ask EXACTLY: "Would you like to provide any contact details so we can follow up with you? This is **COMPLETELY OPTIONAL**. You may say 'no' or 'skip' to remain anonymous." (Ensure 'COMPLETELY OPTIONAL' is Bold and Uppercase).
- **ANYTHING ELSE**:
  - After user provides contact info OR says "no/skip", you MUST ask: "Is there anything else you would like to add or clarify before I submit your report?"
- **FINALIZATION**: 
  - ONLY if user says "No" to "Anything else?", your NEXT response MUST be the final Case ID message.
  - Do NOT summarize facts first.

────────────────────────────────
🚫 RESTRICTIONS (CRITICAL)
────────────────────────────────

1. **NEVER output a "Confirmed Facts" summary** to the user. The [CONFIRMED FACTS] block is for YOUR eyes only.
2. **Do NOT re-ask** for details already present in [CONFIRMED FACTS].
3. **Do NOT add pleasantries** after the final message.

────────────────────────────────
🧾 FINALIZATION MESSAGE
────────────────────────────────

When finished (user says "no" to anything else), say EXACTLY this:

"Thank you for your courage in reporting this. Your Case ID is CASE_ID_PLACEHOLDER. Your Secret Key is SECRET_KEY_PLACEHOLDER. Please save these details to track your case. We will investigate and take appropriate action. You've done the right thing by speaking up."

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
    
    GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
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
                print(f"[LLM_AGENT] Attempt {attempt+1} failed: {e}", flush=True)
                import traceback
                traceback.print_exc()
                if attempt < max_retries: 
                    await asyncio.sleep(1)
                else:
                    print(f"[LLM_AGENT] All retries exhausted, falling back to mock", flush=True)
        
        print(f"[LLM_AGENT] Falling back to mock chat", flush=True)
        return await LLMAgent._mock_chat(conversation_history, current_state)

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

        # 4. AGGRESSIVE JSON STRIPPING (At the end of message)
        # Matches a closing JSON block at the very end of the string, even if no markdown tags
        # Logic: Look for last occurrence of } and check if it looks like a JSON object started recently
        # We can simply remove any trailing block that looks like { "key": ... } using regex
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
