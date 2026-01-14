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
- A form
- A police officer
- A legal authority
- A motivational speaker
- A system or machine

You do NOT over-emphasize emotions or bravery.
Avoid phrases like “this takes a lot of courage” unless the user explicitly expresses fear or distress.

Keep responses concise and natural.
Ideal length: 1–2 short sentences.
Occasionally 3 sentences only when clarification is needed.

Avoid dramatic reassurance.
Be steady, grounded, and matter-of-fact.

────────────────────────────────
🔐 TRUST & ANONYMITY (VERY IMPORTANT)
────────────────────────────────

- Clearly convey that sharing identity is NOT required.
- NEVER ask for name, phone number, ID, or contact details.
- If the user hesitates, refuses, or says “no”:
  - Acknowledge briefly
  - Respect their choice
  - Offer to pause or continue later
  - Do NOT repeat the same question verbatim
  - Do NOT pressure or persuade

Do not restart the conversation or re-greet the user.

────────────────────────────────
🎯 YOUR OBJECTIVE
────────────────────────────────

Your goal is to collect details of a corruption incident conversationally and accurately.

You must gather the following **five details**, one at a time:

1. WHAT  
   A clear explanation of what happened.

2. WHERE  
   You MUST collect ALL FOUR DETAILS:
   - City
   - State
   - Specific Location (Building/Office/Area)
2. WHERE  
   You MUST collect ALL FOUR DETAILS:
   - City
   - State
   - Specific Location (Building/Office/Area)
   - Landmark
   
   CRITICAL: Do NOT ask for "When" or move forward until ALL 4 are collected.
   If user provides partial info (e.g., just "Sector 5"), ask: "Which City and State is Sector 5 in?"
   EXTRACTION RULE: If user says "Flock STR, Sector 45, Gurugram", extract the ENTIRE string. Do not mark as "unknown".

3. WHEN  
   Date AND Time. Both are STRICTLY required.
   If user provides Date only (e.g., "Jan 12"), ask: "What time did this happen?"
   Reject vague answers.

4. WHO  
   Names or roles of the people involved.
   If user provides Role (e.g., "Senior Officer"), ask for the Name. Do NOT ask for "Name or Role" if you have one.

5. EVIDENCE  
   Whether any evidence exists, with a short description.

────────────────────────────────
🧭 CONVERSATION RULES (CRITICAL)
────────────────────────────────

- Ask ONLY ONE question per message.
- Use a calm, steady, and reassuring tone. Give the user space to talk.
- Never combine questions.
- Never ask for details already present in the [CONFIRMED FACTS] block.

If an answer is **vague or incomplete**:
- Acknowledge what was provided with empathy.
- Speak like a human assistant (e.g. "I understand. To submit the report, I specifically need the City name.").
- Clearly state what is missing.
- Ask only for the missing part.

Persona Check:
- Be matter-of-fact but kind.
- Avoid sounding like a machine or a rigid form.
- If the user provides a location (landmark, sector, area), accept it as the location. Do NOT repeatedly ask for more specifics.
- Do NOT use words like "approximately", "rough", "guess". Be precise.

You must NOT:
- Re-greet the user
- Restart the flow
- Loop the same question endlessly
- Summarize the entire case mid-conversation

────────────────────────────────
🗂️ CONFIRMED FACTS AWARENESS
────────────────────────────────

At the top of the conversation, there is a [CONFIRMED FACTS] block.

- Treat it as the single source of truth.
- NEVER ask for information already present.
- Use it to decide what to ask next.
- Progress logically from one missing detail to the next.

────────────────────────────────
🧾 FINALIZATION BEHAVIOR
────────────────────────────────

Once ALL five details are confidently gathered, say EXACTLY this:

"Thank you for your courage in reporting this. Your Case ID is CASE_ID_PLACEHOLDER. Your Secret Key is SECRET_KEY_PLACEHOLDER. Please save these details to track your case. We will investigate and take appropriate action. You've done the right thing by speaking up."

Do NOT add anything before or after this message.

────────────────────────────────
🧩 STRUCTURED DATA EXTRACTION (INTERNAL USE)
────────────────────────────────

At the VERY END of your response, you MUST include a JSON block with the best extracted data.

IMPORTANT:
- Even if [CONFIRMED FACTS] has data, you MUST output it in this JSON block to persist it.
- If you don't output the JSON, the system will forget the details.
- Use empty strings "" for unknown fields.

Format EXACTLY like this:

```json
{
  "what": "",
  "where": "",
  "when": "",
  "who": "",
  "evidence": ""
}
"""



class LLMAgent:
    """Groq-powered LLM Agent."""
    
    GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
    GROQ_MODEL = "llama-3.1-8b-instant"
    
    @staticmethod
    async def chat(conversation_history: list, current_state: dict = None) -> Tuple[str, Optional[dict]]:
        print(f"[LLM_AGENT] Starting chat for session. History length: {len(conversation_history)}")
        api_key = settings.GROQ_API_KEY
        if not api_key:
            print("[LLM_AGENT] No API Key found. Using Mock Fallback.")
            return await LLMAgent._mock_chat(conversation_history, current_state)

        # 1. LOCAL FACT SCRAPER (Safety Net)
        state = current_state.copy() if current_state else {}
        last_user_msg = conversation_history[-1]["content"].lower() if conversation_history else ""
        
        # 2. Build the PROGRESS SUMMARY (LLM is sole authority)
        summary_parts = []
        for k in ["what", "where", "when", "who", "evidence"]:
            val = state.get(k)
            if val and val not in ["...", "", "none", "unknown"]:
                summary_parts.append(f"- {k.upper()}: {val[:200]}")
        
        # --- FACT SHIELD (Force-fill common missing facts if detected in history) ---
        all_user_msgs = " ".join([m["content"].lower() for m in conversation_history if m["role"] == "user"])
        
        # Story Detection: Higher threshold for "Complete" narrative, but lower for "Some Narrative"
        has_narrative = len(all_user_msgs) > 20 or any(k in all_user_msgs for k in ["bribe", "money", "corrupt", "incident", "happened"])
        
        if "- WHAT:" not in "\n".join(summary_parts) and has_narrative:
            summary_parts.insert(0, "- WHAT: [Narrative provided in history]")
            
        # Location Scraper: Acknowledge partial details but don't mark as "Complete"
        # We only inject this to prevent the AI from RE-ASKING for the same landmark.
        has_loc_mentions = any(k in all_user_msgs for k in ["sector", "office", "station", "building", "street", "road", "block", "floor", "area"])
        
        # Heuristic: If user just gave a short answer, they likely provided the missing city.
        # Don't inject the "missing" note which causes the AI to ignore the new input.
        is_short_answer = len(last_user_msg) < 60
        
        if "- WHERE:" not in "\n".join(summary_parts) and has_loc_mentions and not is_short_answer:
             summary_parts.append("- WHERE: [Landmark mentioned. Verify if CITY is present in history.]")
        # ----------------------------------------------------------------------------

        summary_text = "\n".join(summary_parts) if summary_parts else "No information yet."

        # 3. Construct messages
        full_system_prompt = f"{SYSTEM_PROMPT}\n\n### [CONFIRMED FACTS] ###\n{summary_text}\n##########################"
        
        # Determine if new evidence was just uploaded EARLY so it can be used in message construction
        has_evidence_injection = any("[NEW EVIDENCE UPLOADED]" in m.get("content", "") for m in conversation_history if m.get("role") == "system")

        # Determine the last user message for potential injection
        user_message_content = conversation_history[-1]["content"] if conversation_history else ""
        if has_evidence_injection and not user_message_content.strip():
            user_message_content = "[User uploaded a marked evidence file.]"

        messages = [{"role": "system", "content": full_system_prompt}]
        # Increase history to 10 messages to maintain critical context
        recent_history = conversation_history[-10:] if len(conversation_history) > 10 else conversation_history
        for msg in recent_history:
            # If this is the last user message and we've injected content, use the injected content
            if msg == recent_history[-1] and msg["role"].lower() == "user" and has_evidence_injection and not msg["content"].strip():
                messages.append({"role": msg["role"].lower(), "content": user_message_content})
            else:
                messages.append({"role": msg["role"].lower(), "content": msg["content"]})
            
        # 4. DETERMINATIONS (Trusting LLM for field completeness)
        # Fix: Define has_evidence_injection properly before using it
        has_evidence_injection = any("[NEW EVIDENCE UPLOADED]" in m["content"] for m in messages if m["role"] == "system")
        
        # Detection of info in HISTORY (Ensured sticky state)
        # Use a more balanced check for has_story
        has_story = state.get("what") or len(all_user_msgs) > 30 or has_evidence_injection
        
        next_missing = "Story/What"
        if has_story:
            # === EVIDENCE CHECK FIRST (If just uploaded, skip all others) ===
            if has_evidence_injection:
                next_missing = "Evidence Acknowledgement"
            elif not state.get("where") and "sector" not in last_user_msg and "office" not in last_user_msg and "station" not in last_user_msg:
                next_missing = "Location"
            # SMART DATE/TIME CHECK
            elif not state.get("when"):
                 next_missing = "Time/Date"
            # ENFORCE STRICT TIME CHECK: If we have a value but NO time, force ask again
            elif state.get("when") and not re.search(r'\d{1,2}:\d{2}|am|pm|morning|evening|night|afternoon|noon', str(state["when"]), re.IGNORECASE):
                 print(f"[LLM_AGENT] DEBUG: Strict Time Check Triggered. Current 'when': {state['when']}")
                 next_missing = "Time (Missing)"
            # ENFORCE STRICT DATE CHECK: If we have time but no date
            elif state.get("when") and not re.search(r'jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec|\d{1,2}/|\d{4}|yesterday|today|tomorrow', str(state["when"]), re.IGNORECASE):
                 print(f"[LLM_AGENT] DEBUG: Strict Date Check Triggered. Current 'when': {state['when']}")
                 next_missing = "Date (Missing)"
            elif not state.get("who"):
                next_missing = "Who (Offender)"
            elif not state.get("evidence") and not has_evidence_injection:
                next_missing = "Evidence"
            # NEW STEP: Contact Info (Explicitly Optional)
            elif not state.get("contact_info_asked"):
                next_missing = "Optional Contact Info"
            # NEW STEP: Final Confirmation
            elif not state.get("final_confirmation_asked"):
                next_missing = "Final Confirmation"
            else:
                next_missing = "COMPLETE"
        
        print(f"[LLM_AGENT] DEBUG: Calculated next_missing = {next_missing}")

        # 5. PROGRAMMATIC BYPASS (ANONYMITY & REFUSAL)
        last_msg_content = conversation_history[-1]["content"].lower() if conversation_history else ""
        refusal_keywords = ["anonymous", "no thanks", "no", "skip", "don't want", "dont want", "not now", "no i dont", "no i don't"]
        
        if "optional" in next_missing.lower() or next_missing == "COMPLETE" or next_missing == "Final Confirmation":
             if any(k in last_msg_content for k in refusal_keywords):
                 # If user refuses contact, mark it and move to final confirmation
                 if "contact" in next_missing.lower():
                     state["contact_info_asked"] = True
                     state["contact_info"] = "Anonymous"
                     return "Understood. Your report will remain anonymous. Is there anything else you would like to add before I finalize?", state
                 
                 # If user confirms they have nothing else to add, finalize
                 closing_text = """Thank you for your courage.
Your Case ID is: CASE_ID_PLACEHOLDER
Your Secret Key is: SECRET_KEY_PLACEHOLDER

IMPORTANT: Please save this Case ID and Secret Key safely. You will need them to check your case status. We cannot recover them if lost.

We will investigate and take appropriate action. You've done the right thing by speaking up."""
                 return closing_text, state

        # 6. Construct Payload
        payload = {
            "model": LLMAgent.GROQ_MODEL,
            "messages": messages,
            "temperature": 0.1, 
            "max_tokens": 1024
        }
        
        headers = {
            "Authorization": f"Bearer {settings.GROQ_API_KEY.strip()}",
            "Content-Type": "application/json"
        }
        
        # RETRY LOGIC for Rate Limits
        max_retries = 2
        for attempt in range(max_retries + 1):
            try:
                print(f"[LLM_AGENT] Attempt {attempt+1}/{max_retries+1} sending request to {LLMAgent.GROQ_API_URL}...")
                
                async with httpx.AsyncClient() as client:
                    response = await client.post(
                        LLMAgent.GROQ_API_URL, json=payload, headers=headers, timeout=30.0
                    )
                    
                    if response.status_code == 200:
                        data = response.json()
                        text_response = data["choices"][0]["message"]["content"]
                        print(f"[LLM_AGENT] Success. Raw Response length: {len(text_response)}")
                        
                        # 5. Extract fresh JSON from AI (Renumbering for consistency)
                        fresh_extracted = LLMAgent._extract_report(text_response) or {}
                        
                        # 6. Merge with our high-confidence local findings (Aggressive Sticky Logic)
                        final_report_to_save = state.copy()
                        
                        # Helper to check if a value is "empty"
                        def is_empty_val(v):
                            if not v: return True
                            v_lower = str(v).strip().lower()
                            return v_lower in ["...", "none", "unknown", "n/a", "not specified", "null", "undefined", ""]

                        for k, v in fresh_extracted.items():
                            val = str(v).strip()
                            
                            # SAFETY 1: If new value is practically empty, ignore it completely
                            if is_empty_val(val):
                                continue
                                
                            current_val = str(state.get(k) or "").strip()
                            
                            # SAFETY 2: If we have no current value (or it's empty), take the new one
                            if is_empty_val(current_val):
                                final_report_to_save[k] = val
                            
                            # SAFETY 3: If we DO have a current value, be very careful
                            else:
                                # Logic: Only update if the new value is SIGNIFICANTLY different and NOT "worse"
                                # e.g. "Delhi" vs "Delhi, India" -> Accept "Delhi, India"
                                # e.g. "Delhi, India" vs "Delhi" -> Keep "Delhi, India"
                                
                                # If the new value contains the old value, it's likely an expansion -> UPDATE
                                if current_val.lower() in val.lower() and len(val) > len(current_val):
                                    final_report_to_save[k] = val
                                    
                                # If the old value contains the new value, it's a contraction -> IGNORE (Keep old)
                                elif val.lower() in current_val.lower():
                                    continue
                                    
                                # If completely different, assume correction -> UPDATE
                                else:
                                    final_report_to_save[k] = val
                                    
                        clean_response = LLMAgent._clean_response(text_response)
                        
                        # --- RESPONSE GUARD (Hard Lock against Redundancy) ---
                        lower_resp = clean_response.lower()
                        
                        # Define keyword clusters for each topic
                        field_keywords = {
                            "what": ["what happened", "describe the incident", "led you to report", "elaborate", "tell me about", "more details", "incident description"],
                            "where": ["city", "state", "located in", "exact location", "where this happened", "location"],
                            "when": ["date", "time", "when this occurred", "occurred on", "approximate time"],
                            "who": ["name", "role", "official", "who was involved", "person in charge"],
                            "evidence": ["evidence", "documents", "files", "attachment", "upload"]
                        }
                        
                        # Determine if the AI is re-asking for a topic we already have
                        should_force_move = False
                        for field, keywords in field_keywords.items():
                            # Special case for 'what': use has_story logic
                            status_exists = has_story if field == "what" else (state.get(field) and state[field] not in ["...", "", "none", "unknown"])
                            
                            # Only trigger if status exists AND the response is likely a QUESTION about it
                            # We check for "?" to be safer, or specific "tell me" phrases
                            if status_exists:
                                hits = [k for k in keywords if k in lower_resp]
                                if hits:
                                    # Check if it's actually asking
                                    if "?" in clean_response or "tell me" in lower_resp or "provide" in lower_resp:
                                        should_force_move = True
                                        break
                        
                        # FIX: If we just uploaded evidence, FORCE the acknowledgement flow immediately.
                        # Do NOT let the LLM's natural response (which may mention city/location) pass through.
                        if has_evidence_injection:
                            should_force_move = False
                            # EXPLICIT OVERRIDE: Force acknowledgement + Contact Info question
                            final_report_to_save["evidence"] = "Uploaded"
                            clean_response = """I have received your evidence file. Thank you for sharing this.

Would you like to provide any contact details so we can follow up with you? This is **COMPLETELY OPTIONAL**. You may say 'no' or 'skip' to remain anonymous."""
                            return clean_response, final_report_to_save

                        if should_force_move:
                            # Search for the next missing field to "move" the AI to
                            if not has_story:
                                clean_response = "I understand. To help me get a better picture, could you please share a few more details about what happened?"
                            elif not (state.get("where") and state["where"] not in ["...", "", "none", "unknown"]):
                                # Only ask once, don't loop. Let the LLM handle it naturally.
                                clean_response = "Could you please tell me where this took place? A city name or specific office/location would help."
                            
                            # SMART DATE/TIME RE-PROMPT
                            elif not (state.get("when") and state["when"] not in ["...", "", "none", "unknown"] and re.search(r'\d{1,2}:\d{2}|am|pm|morning|evening|night|afternoon|noon', str(state["when"]), re.IGNORECASE)):
                                # Check what we have so far
                                current_when = str(state.get("when", "")).lower()
                                has_date = any(x in current_when for x in ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec", "/", "tomorrow", "yesterday", "today"])
                                has_time = any(x in current_when for x in ["am", "pm", ":", "o'clock", "morning", "evening", "night", "noon"])
                                
                                if has_date and not has_time:
                                    clean_response = "I have the date. Could you please provide the **Time** when this happened?"
                                elif has_time and not has_date:
                                    clean_response = "I have the time. Could you please provide the **Date** when this happened?"
                                else:
                                    clean_response = "I have the location details. Could you please provide the **Date AND Time** when this happened? Both are strictly required for the report."

                            elif not (state.get("who") and state["who"] not in ["...", "", "none", "unknown"]):
                                clean_response = "I have that noted. To be precise, could you provide the **Name** of the person involved? (If you only know the Role, that is fine too)."
                            elif not (state.get("evidence") and state["evidence"] not in ["...", "", "none", "unknown"]):
                                clean_response = "Thank you for these details. If you have any documents, photos, or evidence you'd like to share, you can upload them here. If not, just let me know."
                            
                            # NEW: Contact Info Step (Explicitly Optional)
                            elif not state.get("contact_info_asked"):
                                final_report_to_save["contact_info_asked"] = True
                                clean_response = "Would you like to provide any contact details so we can follow up with you? This is **COMPLETELY OPTIONAL**. You may say 'no' or 'skip' to remain anonymous."
                            
                            # NEW: Final Confirmation Step
                            elif not state.get("final_confirmation_asked"):
                                final_report_to_save["final_confirmation_asked"] = True
                                clean_response = "Is there anything else you would like to add before I finalize your report?"
                            
                            else:
                                # COMPLETION / FINALIZATION
                                if "CASE_ID_PLACEHOLDER" not in clean_response:
                                    clean_response = "Thank you for being so thorough. Your report is complete. Your Case ID is: CASE_ID_PLACEHOLDER. Your Secret Key is: SECRET_KEY_PLACEHOLDER. Please save these details safely."

                                # Force-inject Secret Key if missing (Safety Net)
                                if "CASE_ID_PLACEHOLDER" in clean_response and "SECRET_KEY_PLACEHOLDER" not in clean_response:
                                    clean_response += "\n\nYour Secret Key is: SECRET_KEY_PLACEHOLDER"

                                # Force-inject Safety Warning
                                if "cannot recover" not in clean_response.lower():
                                    clean_response += "\n\n**IMPORTANT: Save your Case ID and Secret Key now. We cannot recover them if lost.**"
                        # -----------------------------------------------------

                        return clean_response, final_report_to_save
                        
                    elif response.status_code == 429:
                        print(f"[LLM_AGENT] Rate Limit 429 Hit. Waiting 10 seconds...")
                        await asyncio.sleep(10)
                        continue # Retry
                        
                    else:
                        try:
                            error_detail = response.json()
                        except:
                            error_detail = response.text
                        print(f"[LLM_AGENT] Groq Error: {response.status_code} - {error_detail}")
                        return ("Technical difficulty. Please try again.", None)

            except Exception as e:
                print(f"[LLM_AGENT] Exception on attempt {attempt}: {e}")
                if attempt < max_retries:
                    await asyncio.sleep(2)
                    continue
                else:
                    print(f"[LLM_AGENT] Max retries exceeded. Falling back to Mock.")
                    return await LLMAgent._mock_chat(conversation_history, current_state)
        
        return ("Technical difficulty. Please try again later.", None)
    
    @staticmethod
    async def _mock_chat(conversation_history: list, current_state: dict = None) -> Tuple[str, Optional[dict]]:
        """
        Rule-based fallback with compassionate persona.
        """
        state = current_state.copy() if current_state else {}
        last_user_msg = conversation_history[-1]["content"].lower() if conversation_history else ""
        
        # 1. Update State (Simple Keyword Extraction)
        if "bribe" in last_user_msg or "money" in last_user_msg: state["what"] = "Bribery incident"
        if "office" in last_user_msg or "station" in last_user_msg: state["where"] = "Office location"
        
        # 2. Determine Next Question with Warmth
        if not state.get("what"):
            return ("Thank you for reaching out. I'm here to listen and help you report this safely. Could you share a bit about what happened?", state)
        if not state.get("where"):
            return ("Can you now please provide the location?", state)
        if not state.get("when"):
            return ("That's very helpful. Could you please provide the **Date AND Time** when this occurred? Both are strictly required.", state)
        if not state.get("who"):
            return ("I understand. Do you know the name or role of the official involved, or which office they belong to?", state)
        if not state.get("evidence"):
            return ("Thank you for being so thorough. If you have any documents or evidence, you can share them here, or just tell me about them. (Simply type 'none' to skip)", state)
        
        # 3. Final Conclusion
        return ("Thank you so much for your courage in reporting this. Your session is complete.\n\nYour Case ID is: CASE_ID_PLACEHOLDER\nYour Secret Key is: SECRET_KEY_PLACEHOLDER\n\nPlease keep this safe to check your status later.", state)
    @staticmethod
    def _clean_response(text: str) -> str:
        print(f"[LLM_AGENT] Cleaning response... {len(text)} chars")
        # 1. Remove backticked JSON block
        text = re.sub(r'```json\s*\{[\s\S]*?\}\s*```', '', text, flags=re.DOTALL)
        # 2. Remove Thought block (Dotall mode)
        text = re.sub(r'<thought>[\s\S]*?</thought>', '', text, flags=re.DOTALL)
        # 3. Remove inline JSON structures more safely
        text = re.sub(r'\{\s*"what"[\s\S]*?\}', '', text)
        
        # 4. Remove any other potential artifacts
        text = text.replace("Null", "").replace("None", "")
        
        cleaned = re.sub(r'\n{3,}', '\n\n', text).strip()
        print(f"[LLM_AGENT] Cleaned output length: {len(cleaned)}")

        if not cleaned or len(cleaned) < 3:
            return "Reference Code: EVD-NULL. I received your input. Is there anything else you'd like to add?"
        return cleaned
        # 4. Remove [CONFIRMED FACTS] block if leaked
        text = re.sub(r'###\s*\[CONFIRMED FACTS\]\s*###[\s\S]*?##########################', '', text, flags=re.DOTALL)
        
        cleaned = re.sub(r'\n{3,}', '\n\n', text).strip()
        if not cleaned:
            return "Reference Code: EVD-NULL. I received your input. Is there anything else you'd like to add?"
        return cleaned
    
    @staticmethod
    def _extract_report(text: str) -> Optional[dict]:
        # 1. Try finding JSON inside code blocks first
        matches = re.findall(r'```json\s*(\{[\s\S]*?\})\s*```', text)
        if not matches:
            # 2. Try finding anything that looks like a JSON object containing "what"
            matches = re.findall(r'(\{[\s\S]*?"what"[\s\S]*?\})', text)
            
        if matches:
            try:
                # Get the last match
                json_str = matches[-1].strip()
                # Remove common LLM-isms like trailing commas or explanation text
                # We'll try to find the last closing brace
                last_brace = json_str.rfind('}')
                if last_brace != -1:
                    json_str = json_str[:last_brace+1]
                
                return json.loads(json_str)
            except Exception as e:
                # LAST RESORT: Try to find keys manually if JSON is broken
                extracted = {}
                for key in ["what", "where", "when", "who", "evidence", "contact_info"]:
                    match = re.search(rf'"{key}"\s*:\s*"(.*?)"', json_str)
                    if match:
                        extracted[key] = match.group(1)
                if extracted: return extracted
                print(f"[LLM_AGENT] JSON Extraction Error: {e}")
        return None
    
    @staticmethod
    async def extract_fields(conversation_history: list) -> dict:
        return {}
        
    @staticmethod
    async def rewrite_update(raw_text: str) -> str:
        """
        Rewrites an NGO update to be neutral, factual, and public-safe.
        """
        # Specific System Prompt for Updates
        UPDATE_SYSTEM_PROMPT = """You are rewriting official case status updates for public display.

Rules:
- Use clear, neutral, factual language
- Maximum 1-2 sentences
- Do NOT add new information
- Do NOT speculate or assume
- Do NOT include names, phone numbers, emails, or locations
- Do NOT use emotional or judgmental language"""

        UPDATE_USER_PROMPT = f"""Rewrite this update clearly for a citizen:
"{raw_text}" """

        api_key = settings.GROQ_API_KEY
        if not api_key:
            return f"[MOCK REWRITE] {raw_text}"

        messages = [
            {"role": "system", "content": UPDATE_SYSTEM_PROMPT},
            {"role": "user", "content": UPDATE_USER_PROMPT}
        ]
        
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": "llama-3.3-70b-versatile", # Use Versatile for better logic
            "messages": messages,
            "temperature": 0.1, # Low temp for factual consistency
            "max_tokens": 150
        }

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    LLMAgent.GROQ_API_URL, json=payload, headers=headers, timeout=30.0
                )
                if response.status_code == 200:
                    data = response.json()
                    return data["choices"][0]["message"]["content"].strip()
        except Exception as e:
            print(f"[LLM_AGENT] Rewrite failed: {e}")
            return raw_text

    @staticmethod
    async def analyze_image_fast(file_path: str, known_mime_type: str = None) -> str:
        """
        FAST Visual Description using Groq Llama 3.2 Vision.
        Used for immediate chat confirmation (Stage A).
        """
        api_key = settings.GROQ_API_KEY
        if not api_key: 
            print("[LLM_AGENT] Fast Vision Skipped: No API Key")
            return "Visual content detected (System configured without Vision Key)"
        
        try:
            import base64
            import mimetypes
            
            # Use known mime type from DB if available, else guess
            mime_type = known_mime_type
            if not mime_type:
                mime_type, _ = mimetypes.guess_type(file_path)
            
            if not mime_type or not mime_type.startswith("image"):
                print(f"[LLM_AGENT] Fast Vision Skipped: Invalid Mime {mime_type} for {file_path}")
                return "File attachment detected"
                
            with open(file_path, "rb") as image_file:
                encoded_string = base64.b64encode(image_file.read()).decode('utf-8')
                
            data_url = f"data:{mime_type};base64,{encoded_string}"
            
            payload = {
                "model": "llama-3.2-11b-vision-preview", # Corrected model name
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": "Describe this image in 1 short sentence (max 15 words). Focus on visual content (e.g. 'screenshot of text', 'photo of a building'). Do NOT analyze meaning."},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": data_url
                                }
                            }
                        ]
                    }
                ],
                "temperature": 0.1,
                "max_tokens": 50
            }
            
            headers = {
                "Authorization": f"Bearer {settings.GROQ_API_KEY.strip()}",
                "Content-Type": "application/json"
            }
            
            print(f"[LLM_AGENT] Sending Fast Vision Request for {file_path} using llama-3.2-11b-vision-preview...")
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    LLMAgent.GROQ_API_URL, json=payload, headers=headers, timeout=15.0
                )
                if response.status_code == 200:
                    data = response.json()
                    desc = data["choices"][0]["message"]["content"].strip()
                    print(f"[LLM_AGENT] Fast Vision Success: {desc}")
                    return desc
                else:
                    print(f"[LLM_AGENT] Fast Vision API Error {response.status_code}: {response.text}")
                    return "Image content detected (Analysis unavailable)"
                    
        except Exception as e:
            print(f"[LLM_AGENT] Fast Vision Exception: {e}")
            return "Image content detected"

    @staticmethod
    async def analyze_audio_fast(file_path: str) -> str:
        """
        Transcribe audio using Groq Whisper.
        """
        api_key = settings.GROQ_API_KEY
        if not api_key:
            print("[LLM_AGENT] Audio Analysis Skipped: No API Key")
            return "Audio content detected"

        try:
            # Groq currently supports whisper-large-v3
            # We need to send multipart/form-data
            
            print(f"[LLM_AGENT] Sending Audio to Whisper: {file_path}")
            
            async with httpx.AsyncClient() as client:
                with open(file_path, "rb") as f:
                    files = {"file": (os.path.basename(file_path), f, "audio/mpeg")}
                    data = {"model": "whisper-large-v3", "temperature": 0, "response_format": "json"}
                    
                    response = await client.post(
                        "https://api.groq.com/openai/v1/audio/transcriptions",
                        files=files,
                        data=data,
                        headers={"Authorization": f"Bearer {api_key}"},
                        timeout=30.0
                    )
                    
                    if response.status_code == 200:
                        transcription = response.json().get("text", "")
                        print(f"[LLM_AGENT] Whisper Success: {transcription[:50]}...")
                        # Limit length for context
                        if len(transcription) > 200:
                            return f"Audio Transcript: \"{transcription[:200]}...\""
                        return f"Audio Transcript: \"{transcription}\""
                    else:
                        print(f"[LLM_AGENT] Whisper Error {response.status_code}: {response.text}")
                        return "Audio content detected (Transcription unavailable)"

        except Exception as e:
            print(f"[LLM_AGENT] Audio Analysis Exception: {e}")
            return "Audio content detected"
