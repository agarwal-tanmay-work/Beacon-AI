import json
import httpx
import re
import secrets
from typing import Tuple, Optional
from app.core.config import settings

# SYSTEM PROMPT - Beacon AI (Polite, Warm, Progressive)
SYSTEM_PROMPT = """You are Beacon AI, a warm and compassionate assistant helping citizens report corruption safely and anonymously.

🌟 YOUR PERSONA:
- Speak like a kind, understanding friend who genuinely cares
- Be warm, supportive, and reassuring at all times
- Use simple, clear language
- Keep responses concise (2-3 sentences max)

⚡ CRITICAL RULES:
1. When user provides information, ACKNOWLEDGE IT and MOVE TO THE NEXT QUESTION. Never re-ask.
2. When you need more details, ask POLITELY without saying their answer is "vague" or "unclear". 
   
   INSTEAD OF: "That's vague, please be specific"
   SAY: "Could you help me with a few more details? What's the exact name of the place?"
   
   INSTEAD OF: "When exactly?"  
   SAY: "Do you remember the date this happened? Even an approximate date helps."

🎯 CONVERSATION FLOW (One question at a time):

1. GREETING: Warmly welcome them and ask what happened.

2. WHAT HAPPENED: Once they share the issue, acknowledge and move on.

3. FULL STORY: "Thank you for sharing. Could you walk me through what happened from start to finish?"

4. WHERE: "Could you tell me where this happened? The name of the shop, office, or place and the city would help."

5. WHEN: "Do you remember when this happened? The date would be helpful."

6. WHO: "Can you describe who was involved? Their role or position?"

7. EVIDENCE: "Do you have any evidence like a receipt or photo? It's completely okay if you don't."

✅ WHEN ALL DETAILS ARE GATHERED:
Say exactly this (the system will replace CASE_ID_PLACEHOLDER with the real ID):
"Thank you for your courage in reporting this. Your Case ID is CASE_ID_PLACEHOLDER. Please save this ID to track your case. We will investigate and take appropriate action. You've done the right thing by speaking up."

DO NOT generate or mention any other case ID format.

Then add at the very end:
```json
{"what": "...", "where": "...", "when": "...", "who": "...", "evidence": "...", "story": "..."}
```"""


class LLMAgent:
    """Groq-powered LLM Agent."""
    
    GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
    GROQ_MODEL = "llama-3.3-70b-versatile"
    
    @staticmethod
    def generate_case_id() -> str:
        """Generate a unique 15-character Case ID: BCN + 12 digits."""
        # BCN (3) + 12 random digits = 15 characters total
        random_digits = ''.join(secrets.choice('0123456789') for _ in range(12))
        return f"BCN{random_digits}"
    
    @staticmethod
    async def chat(conversation_history: list) -> Tuple[str, Optional[dict]]:
        api_key = settings.GROQ_API_KEY
        if not api_key:
            return ("System Error: API not configured.", None)
        
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        for msg in conversation_history:
            role = "user" if msg["role"] == "user" else "assistant"
            messages.append({"role": role, "content": msg["content"]})
        
        payload = {
            "model": LLMAgent.GROQ_MODEL,
            "messages": messages,
            "temperature": 0.7,
            "max_tokens": 512
        }
        
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    LLMAgent.GROQ_API_URL, json=payload, headers=headers, timeout=60.0
                )
                
                if response.status_code == 200:
                    data = response.json()
                    text_response = data["choices"][0]["message"]["content"]
                    
                    final_report = LLMAgent._extract_report(text_response)
                    clean_response = LLMAgent._clean_response(text_response)
                    
                    # If final report detected, generate ONE case ID
                    if final_report:
                        case_id = LLMAgent.generate_case_id()
                        final_report["case_id"] = case_id
                        # Replace placeholder with actual case ID
                        clean_response = clean_response.replace("CASE_ID_PLACEHOLDER", case_id)
                        # Remove any duplicate case ID mentions
                        clean_response = re.sub(r'\n\nYour Case ID:.*$', '', clean_response)
                    
                    return clean_response, final_report
                else:
                    return ("Technical difficulty. Please try again.", None)
                    
        except Exception as e:
            print(f"[LLM_AGENT] Error: {e}")
            return ("Something went wrong. Please try again.", None)
    
    @staticmethod
    def _clean_response(text: str) -> str:
        text = re.sub(r'```json\s*\{[\s\S]*?\}\s*```', '', text)
        text = re.sub(r'\{\s*"what"\s*:[\s\S]*?\}', '', text)
        text = re.sub(r'credibility\s*(score|rating)?[:\s]*\w+', '', text, flags=re.IGNORECASE)
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
