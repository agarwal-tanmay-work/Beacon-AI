import asyncio
from app.db.session import AsyncSessionLocal
from sqlalchemy import text
import sys
import os

# Add current directory to path so imports work
sys.path.append(os.getcwd())

async def test_connection():
    print("Testing DB Connection...")
    try:
        async with AsyncSessionLocal() as session:
            result = await session.execute(text("SELECT 1"))
            print(f"Connection Successful! Result: {result.scalar()}")
    except Exception as e:
        print(f"Connection Failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_connection())
