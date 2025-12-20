import asyncio
import os
import sys

# Ensure backend dir is in path
sys.path.append(os.getcwd())

from app.core.config import settings
from app.services.llm_agent import LLMAgent

async def test_app_logic():
    print(f"DEBUG: Using API Key from settings: {settings.GEMINI_API_KEY[:10]}...")
    
    # Simulate a typical conversation starting from the app
    history = [
        {"role": "user", "content": "hello"}
    ]
    
    print("DEBUG: Calling LLMAgent.chat()...")
    try:
        response_text, final_report = await LLMAgent.chat(history)
        print(f"RESULT: {response_text}")
        if final_report:
            print(f"REPORT: {final_report}")
    except Exception as e:
        print(f"ERROR: {e}")

if __name__ == "__main__":
    asyncio.run(test_app_logic())
