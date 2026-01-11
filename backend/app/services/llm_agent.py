import json
import httpx
import re
import secrets
from typing import Tuple, Optional
from app.core.config import settings

# SYSTEM_PROMPT - Beacon AI (Compassionate & Accurate)
SYSTEM_PROMPT = """You are Beacon AI, a warm and compassionate assistant helping citizens report corruption safely and anonymously.

🌟 YOUR PERSONA:
- Speak like a kind, understanding friend who genuinely cares
- Be warm, supportive, and reassuring at all times
- Use simple, clear language
- Keep responses concise (2-3 sentences max)

⚡ CRITICAL RULES:
1. When user provides information, ACKNOWLEDGE IT and MOVE TO THE NEXT QUESTION.
2. If the user refuses to answer or gives a vague answer, MAINTAIN YOUR WARM PERSONA, but explain why the detail is helpful and ASK AGAIN. Do not skip important details (What, Where, When).
3. When you need more details, ask POLITELY without saying their answer is "vague" or "unclear". 
   
   INSTEAD OF: "That's vague, please be specific"
   SAY: "Could you help me with a few more details? What's the exact name of the place?"
   
   INSTEAD OF: "When exactly?"  
   SAY: "Do you remember the date this happened? Even an approximate date helps."

📎 EVIDENCE UPLOAD RULE (VERY IMPORTANT):
- If the user mentions having ANY type of evidence (photo, receipt, document, video, screenshot, file, proof, etc.), you MUST ask them to upload it using the upload button.
- Say something like: "That's great that you have evidence! Please upload it using the paperclip/upload button on the left side of the chat. I'll wait for you to upload it."
- WAIT for them to confirm the upload before moving to the next question.
- Do NOT proceed to the next step until they have uploaded or explicitly said they cannot.

🎯 CONVERSATION FLOW (One question at a time):

1. GREETING: Warmly welcome them and ask what happened.

2. WHAT HAPPENED: Once they share the issue, acknowledge and move on.

3. FULL STORY: "Thank you for sharing. Could you walk me through what happened from start to finish?"

4. WHERE: "Could you tell me where this happened? The name of the shop, office, or place and the city would help."

5. WHEN: "Do you remember when this happened? The date would be helpful."

6. WHO: "Can you describe who was involved? Their role or position?"

7. EVIDENCE: "Do you have any evidence like a receipt, photo, document, or video? It's completely okay if you don't."
   - If they say YES or mention having evidence: Ask them to upload it using the upload button.
   - If they say NO: Acknowledge and move to the next step.

8. OPTIONAL PERSONAL DETAILS (Hybrid Anonymity):
   "Finally, reporting is completely anonymous by default. However, if you wish to be contacted / updated, you may optionally provide your name or contact info. This is completely up to you and skipping it will not affect your report. Would you like to add any details?"
- Speak like a kind, understanding friend who genuinely cares.
- Be warm, supportive, and reassuring.
- Keep responses concise (2-3 sentences max).

🎯 YOUR GOAL:
Gather the following 5 details. A [CONFIRMED FACTS] block is at the top. DO NOT ask for items already in that block.
Only ask ONE question at a time.
1. WHAT: The incident story
2. WHERE: City, Location
3. WHEN: Date, Time
4. WHO: Names, Roles
5. EVIDENCE: Boolean and description

✅ WHEN ALL DETAILS ARE GATHERED:
Say exactly this (the system will replace CASE_ID_PLACEHOLDER with the real ID):
"Thank you for your courage in reporting this. Your Case ID is CASE_ID_PLACEHOLDER. Please save this ID to track your case. We will investigate and take appropriate action. You've done the right thing by speaking up."

⛔ CASE ID AND SECRET KEY RULES (ABSOLUTE):
- NEVER generate or invent your own Case ID or Secret Key.
- NEVER use formats like Case-12345, case_id_123, CASE123456, or any numeric ID.
- ONLY use the exact placeholders: CASE_ID_PLACEHOLDER and SECRET_KEY_PLACEHOLDER
- The system will automatically replace them with the correct values.

✅ WHEN ALL DETAILS ARE GATHERED:
Say exactly this (the system will replace placeholders):
"Thank you for your courage in reporting this.

Your Case ID is: CASE_ID_PLACEHOLDER
Your Secret Key is: SECRET_KEY_PLACEHOLDER

⚠️ IMPORTANT: Please save this Secret Key safely. You will need it to check your case status. We cannot recover it if lost.

We will investigate and take appropriate action. You've done the right thing by speaking up."

Then add at the very end:
JSON EXTRACTION (Please include at the very bottom of your response):
```json
{"what": "...", "where": "...", "when": "...", "who": "...", "evidence": "...", "story": "..."}
{"what": "...", "where": "...", "when": "...", "who": "...", "evidence": "..."}
```"""


class LLMAgent:
    """Groq-powered LLM Agent."""
    
    GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
    GROQ_MODEL = "llama-3.3-70b-versatile" # Restored 70B for better accuracy and logic adherence
    
    @staticmethod
    async def chat(conversation_history: list, current_state: dict = None) -> Tuple[str, Optional[dict]]:
        api_key = settings.GROQ_API_KEY
        if not api_key:
            print("[LLM_AGENT] No API Key found. Using Mock Fallback.")
            return await LLMAgent._mock_chat(conversation_history, current_state)

        # 1. LOCAL FACT SCRAPER (Safety Net)
        # Even if a previous JSON extraction failed, we scan history here 
        # to ensure the 'confirmed facts' block is as accurate as possible.
        state = current_state.copy() if current_state else {}
        
        # Keywords for local fallback detection
        for msg in conversation_history:
            if msg["role"] == "user":
                content_lower = msg["content"].lower()
                # Detection patterns (Same as before but used here to augment the state)
                if not state.get("what") and any(kw in content_lower for kw in ["bribe", "charged", "demanded", "asked for money", "corruption", "happened", "extra", "story", "incident", "ice cream", "money", "rupees", "payment"]):
                    state["what"] = msg["content"][:200]
                if not state.get("where") and any(kw in content_lower for kw in ["road", "street", "city", "shop", "office", "area", "delhi", "mumbai", "kalimpong", "store", "located", "place"]):
                    state["where"] = msg["content"][:200]
                if not state.get("when") and any(kw in content_lower for kw in ["yesterday", "today", "last week", "monday", "tuesday", "morning", "evening", "date", "january", "february", "clock", "time", "pm", "am"]):
                    state["when"] = msg["content"][:200]
                if not state.get("who") and any(kw in content_lower for kw in ["officer", "clerk", "shopkeeper", "man", "woman", "manager", "inspector", "person", "staff", "employee"]):
                    state["who"] = msg["content"][:200]
                if not state.get("evidence") and any(kw in content_lower for kw in ["photo", "receipt", "video", "document", "proof", "screenshot", "yes i have", "file", "paperclip"]):
                    state["evidence"] = msg["content"][:200]

        # 2. Build the PROGRESS SUMMARY from the explicit state
        summary_parts = []
        if state.get("what"): summary_parts.append(f"- STORY/WHAT: {state['what'][:100]}...")
        if state.get("where"): summary_parts.append(f"- LOCATION/WHERE: {state['where'][:100]}...")
        if state.get("when"): summary_parts.append(f"- DATE/WHEN: {state['when'][:100]}...")
        if state.get("who"): summary_parts.append(f"- WHO INVOLVED: {state['who'][:100]}...")
        if state.get("evidence"): summary_parts.append(f"- EVIDENCE: {state['evidence'][:100]}...")
        
        summary_text = "\n".join(summary_parts) if summary_parts else "No information yet."

        # 3. Construct messages with summary at the TOP
        full_system_prompt = f"{SYSTEM_PROMPT}\n\n### [CONFIRMED FACTS] ###\nYou already have this information (DO NOT ASK AGAIN):\n{summary_text}\n##########################"
        
        messages = [{"role": "system", "content": full_system_prompt}]
        for msg in conversation_history:
            role = "user" if msg["role"].lower() == "user" else "assistant"
            messages.append({"role": role, "content": msg["content"]})
            
        # 4. Add blunt trailing instruction
        next_missing = "Story/What"
        if state.get("what"): next_missing = "Location/Where"
        if state.get("what") and state.get("where"): next_missing = "Date/When"
        if state.get("what") and state.get("where") and state.get("when"): next_missing = "Who Involved"
        if state.get("what") and state.get("where") and state.get("when") and state.get("who"): next_missing = "Evidence (Invite to upload)"
        
        override_text = f"The user already provided {', '.join(k.upper() for k,v in state.items() if v)}. ASK ONLY about {next_missing} next."
        if all([state.get("what"), state.get("where"), state.get("when"), state.get("who")]):
            if not state.get("evidence"):
                override_text = "Ask if they have any evidence and invite them to use the upload button."
            else:
                override_text = "All info gathered. Conclude the report with the Case ID."

        messages.append({
            "role": "system", 
            "content": f"[SYSTEM OVERRIDE]: {override_text}"
        })
        
        payload = {
            "model": LLMAgent.GROQ_MODEL,
            "messages": messages,
            "temperature": 0.3, 
            "max_tokens": 1024
        }
        
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        
        try:
            print(f"[LLM_AGENT] Calling Groq API...")
            # DEBUG: Print messages to see what context LLM gets
            print(json.dumps(messages, indent=2)) 
            
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    LLMAgent.GROQ_API_URL, json=payload, headers=headers, timeout=60.0
                )
                print(f"[LLM_AGENT] Groq API Response: {response.status_code}")
                
                if response.status_code == 200:
                    data = response.json()
                    text_response = data["choices"][0]["message"]["content"]
                    
                    # 5. Extract fresh JSON from AI
                    fresh_extracted = LLMAgent._extract_report(text_response) or {}
                    
                    # 6. Merge with our high-confidence local scraper findings
                    # This ensures the DB gets the augmented state
                    final_report_to_save = state.copy()
                    for k, v in fresh_extracted.items():
                        if v and v != "...":
                            final_report_to_save[k] = v
                            
                    clean_response = LLMAgent._clean_response(text_response)
                    
                    return clean_response, final_report_to_save
                else:
                    return ("Technical difficulty. Please try again.", None)
                    
        except Exception as e:
            print(f"[LLM_AGENT] Error: {e}. Falling back to Mock.")
            return await LLMAgent._mock_chat(conversation_history, current_state)
    
    @staticmethod
    async def _mock_chat(conversation_history: list, current_state: dict = None) -> Tuple[str, Optional[dict]]:
        """
        Rule-based fallback for demo/offline mode.
        """
        state = current_state.copy() if current_state else {}
        last_user_msg = conversation_history[-1]["content"].lower() if conversation_history else ""
        
        # 1. Update State (Simple Keyword Extraction)
        if "bribe" in last_user_msg or "money" in last_user_msg: state["what"] = "Bribery incident"
        if "delhi" in last_user_msg or "mumbai" in last_user_msg or "office" in last_user_msg: state["where"] = "Government Office"
        if "today" in last_user_msg or "yesterday" in last_user_msg or "202" in last_user_msg: state["when"] = "Recent date"
        if "officer" in last_user_msg or "clerk" in last_user_msg: state["who"] = "Official"
        if "pdf" in last_user_msg or "image" in last_user_msg or "evidence" in last_user_msg: state["evidence"] = "Yes"

        # 2. Determine Next Question
        if not state.get("what"):
            return ("I understand you want to report an incident. Could you briefly describe what happened? (e.g., Was a bribe demanded?)", state)
        if not state.get("where"):
            return ("Thank you. Where did this incident take place? Please mention the city or specific location.", state)
        if not state.get("when"):
            return ("When did this happen? (Date or approximate time)", state)
        if not state.get("who"):
            return ("Do you know the name or designation of the official involved?", state)
        if not state.get("evidence"):
            return ("Do you have any evidence to support this claim? You can upload files or describe what you have.", state)
        
        # 3. Final Conclusion
        return ("Thank you for providing these details. Your report is complete.\n\nYour Case ID is: CASE_ID_PLACEHOLDER\nYour Secret Key is: SECRET_KEY_PLACEHOLDER\n\n⚠️ IMPORTANT: Please save this Secret Key safely. You will need it to check your status.", state)
    
    @staticmethod
    def _clean_response(text: str) -> str:
        # 1. Remove backticked JSON block
        text = re.sub(r'```json\s*\{[\s\S]*?\}\s*```', '', text, flags=re.DOTALL)
        # 2. Remove Thought block (Dotall mode)
        text = re.sub(r'<thought>[\s\S]*?</thought>', '', text, flags=re.DOTALL)
        # 3. Remove inline JSON ONLY if it looks like the specific report structure (Dotall)
        text = re.sub(r'\{\s*"what"\s*:.*?"where"\s*:.*?"when"\s*:.*?"who"\s*:.*?"evidence"\s*:.*?\}', '', text, flags=re.DOTALL)
        return re.sub(r'\n{3,}', '\n\n', text).strip()
    
    @staticmethod
    def _extract_report(text: str) -> Optional[dict]:
        match = re.search(r'```json\s*(\{[\s\S]*?\})\s*```', text)
        if match:
            try:
                return json.loads(match.group(1))
            except:
                pass
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
                else:
                    return raw_text # Fallback to raw if API fails
        except Exception as e:
            print(f"[LLM_AGENT] Rewrite failed: {e}")
            return raw_text
