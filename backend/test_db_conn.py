import asyncio
import sys
import os

# Add the current directory to sys.path to allow importing 'app'
sys.path.append(os.getcwd())

from app.db.session import engine

async def test_conn():
    print("Attempting to connect to the database...")
    try:
        async with engine.connect() as conn:
            print("✅ Successfully connected to the database!")
    except Exception as e:
        print(f"❌ Connection failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(test_conn())
