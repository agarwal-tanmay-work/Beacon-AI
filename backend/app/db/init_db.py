import asyncio
from app.core.network_utils import force_ipv4_resolution

# Apply network patch immediately to fix Render/Supabase IPv6 issues
force_ipv4_resolution()

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
        
        try:
            # Add timeout to fail fast if connection hangs (e.g. firewall/network issues)
            # 10 seconds should be plenty for a healthy connection
            async with asyncio.timeout(10):
                async with engine.begin() as conn:
                    await conn.run_sync(Base.metadata.create_all)
            logger.info("remote_db_init_complete")
        except TimeoutError:
            logger.error("remote_db_init_timeout", message="Connection to database timed out after 10s. Check network/firewall/URL settings.")
            raise
        except Exception as e:
            logger.error("remote_db_init_failed", error=str(e))
            raise
    
    logger.info("db_init_complete")

if __name__ == "__main__":
    asyncio.run(main())
