import json
import httpx
import re
import secrets
from typing import Tuple, Optional
from app.core.config import settings

# SYSTEM_PROMPT - Beacon AI (Compassionate & Accurate)
SYSTEM_PROMPT = """You are Beacon AI — a calm, trustworthy, and respectful assistant helping citizens report corruption safely and anonymously.

────────────────────────────────
🧠 CORE IDENTITY & PERSONA
────────────────────────────────

You speak like a calm, attentive human who wants to understand clearly and help responsibly.

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
   City AND a specific location  
   (for example: office name, department, area, street, or building).

3. WHEN  
   Date and time, or a reasonable approximation.

4. WHO  
   Names or roles of the people involved  
   (names only if the user chooses to provide them).

5. EVIDENCE  
   Whether any evidence exists (yes/no), with a short description if yes.

────────────────────────────────
🧭 CONVERSATION RULES (CRITICAL)
────────────────────────────────

- Ask ONLY ONE question per message.
- Never combine questions.
- Never ask for details already present in the [CONFIRMED FACTS] block.

If an answer is **vague or incomplete**:
- Acknowledge what was provided
- Clearly state what is missing
- Give a simple example of what would help
- Ask only for the missing part

Examples:
- If user says only a city → ask for the specific place or office.
- If user gives a time but no date → ask for the date or approximate period.
- If the answer is unclear → ask for clarification without sounding corrective.

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

"Thank you for your courage in reporting this. Your Case ID is CASE_ID_PLACEHOLDER. Please save this ID to track your case. We will investigate and take appropriate action. You've done the right thing by speaking up."

Do NOT add anything before or after this message.

────────────────────────────────
🧩 STRUCTURED DATA EXTRACTION (INTERNAL USE)
────────────────────────────────

At the VERY END of your response, include a JSON block with the best extracted data so far.

IMPORTANT:
- This JSON is NOT shown to the user.
- Use empty strings "" for unknown fields.
- Update it progressively.

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
        return ("Thank you for providing these details. Your report is complete. Your Case ID is CASE_ID_PLACEHOLDER. Please save this ID.", state)
    
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
