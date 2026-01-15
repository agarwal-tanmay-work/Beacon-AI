import asyncio
import structlog
from app.db.local_db import local_engine, init_local_db
from app.core.config import settings

# If we eventually migrate to a real remote DB, we'd import that engine here
# from app.db.session import engine 

logger = structlog.get_logger()

async def main():
    logger.info("db_init_start")
    
    # 1. Initialize Local SQLite (always needed for staging)
    await init_local_db()
    
    # 2. Initialize Supabase PostgreSQL Tables (if connection string present)
    if settings.DATABASE_URL and "sqlite" not in settings.DATABASE_URL:
        from app.db.session import engine
        from app.db.base import Base
        # Trigger model registration
        from app.models.beacon import Beacon
        from app.models.beacon_update import BeaconUpdate
        from app.models.beacon_message import BeaconMessage
        
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("remote_db_init_complete")
    
    logger.info("db_init_complete")

if __name__ == "__main__":
    asyncio.run(main())
