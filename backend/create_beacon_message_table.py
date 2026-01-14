
import asyncio
import structlog
from app.core.config import settings
from sqlalchemy.ext.asyncio import create_async_engine
from app.db.base import Base
from app.models.beacon_message import BeaconMessage  # Ensure it is registered

# Setup minimal logging
logger = structlog.get_logger()

async def create_tables():
    print("🚀 Starting Manual Table Creation...")
    
    url = settings.DATABASE_URL
    print(f"   Target DB: {url.split('@')[-1]}")
    
    engine = create_async_engine(url, echo=True)
    
    async with engine.begin() as conn:
        print("   Creating tables if not exist...")
        await conn.run_sync(Base.metadata.create_all)
        print("   ✅ Tables created.")
                
    await engine.dispose()
    print("🎉 Done.")

if __name__ == "__main__":
    if "win32" in str(asyncio.get_event_loop_policy()):
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(create_tables())
