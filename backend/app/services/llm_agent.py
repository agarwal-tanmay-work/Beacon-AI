import json
import httpx
import re
import secrets
from typing import Tuple, Optional
from app.core.config import settings

# SYSTEM_PROMPT - Beacon AI (Compassionate & Accurate)
SYSTEM_PROMPT = """You are Beacon AI, a warm and compassionate assistant helping citizens report corruption safely and anonymously.

🌟 YOUR PERSONA:
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

JSON EXTRACTION (Please include at the very bottom of your response):
```json
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
            return ("System Error: API not configured.", None)

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
            print(f"[LLM_AGENT] Error: {e}")
            return ("Something went wrong. Please try again.", None)
    
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
