
import asyncio
import time
from app.services.llm_agent import LLMAgent
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
from app.core.config import settings

async def test_llm():
    print("--- Testing LLM Agent ---")
    start = time.time()
    try:
        # Mock history
        history = [{"role": "user", "content": "Hello via diagnosis script"}]
        response, report = await LLMAgent.chat(history)
        print(f"LLM Response: {response[:50]}...")
        print(f"LLM Latency: {time.time() - start:.2f}s")
    except Exception as e:
        print(f"❌ LLM Failed: {e}")

async def test_db_simple():
    print("\n--- Testing DB Simple Query ---")
    start = time.time()
    try:
        engine = create_async_engine(settings.DATABASE_URL, echo=False)
        async with engine.begin() as conn:
            await conn.execute(text("SELECT 1"))
        print(f"DB Latency: {time.time() - start:.2f}s")
    except Exception as e:
        print(f"❌ DB Failed: {e}")

async def main():
    await test_llm()
    await test_db_simple()

if __name__ == "__main__":
    asyncio.run(main())
