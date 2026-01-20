
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
import os

DATABASE_URL = "postgresql+asyncpg://postgres:TanmayAg@db.myvmzqrkitrqxummzhjw.supabase.co:5432/postgres"

async def check_db():
    print(f"Connecting to {DATABASE_URL}...")
    try:
        engine = create_async_engine(DATABASE_URL)
        async with engine.connect() as conn:
            print("Connected.")
            # Check Beacon count
            res = await conn.execute(text("SELECT count(*) FROM beacon"))
            print(f"Beacon Count: {res.scalar()}")
            
            # Check Reports count
            res = await conn.execute(text("SELECT count(*) FROM reports"))
            print(f"Reports Count: {res.scalar()}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    if os.name == 'nt':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(check_db())
