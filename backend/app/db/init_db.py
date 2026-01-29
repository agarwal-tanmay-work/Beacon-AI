import asyncio
# from app.core.network_utils import force_ipv4_resolution

# Apply network patch immediately to fix Render/Supabase IPv6 issues
# DISABLED: Force IPv4 was blocking IPv6-only Supabase resolution in this environment.
# force_ipv4_resolution() # Commented out to allow IPv6/Supabase connectivity

import structlog
from app.db.local_db import local_engine, init_local_db
from app.core.config import settings

# If we eventually migrate to a real remote DB, we'd import that engine here
# from app.db.session import engine 

logger = structlog.get_logger()

async def run_init_db():
    logger.info("db_init_start")
    
    # 1. Initialize Local SQLite (SKIPPED - MIGRATED TO SUPABASE)
    # await init_local_db()
    
    # 2. Initialize Supabase PostgreSQL Tables (if connection string present)
    if settings.DATABASE_URL and "sqlite" not in settings.DATABASE_URL:
        # Import here to avoid circular dependencies or early initialization
        from app.db.session import engine
        from app.db.base import Base
        # Trigger model registration
        from app.models.beacon import Beacon
        from app.models.beacon_update import BeaconUpdate
        from app.models.beacon_message import BeaconMessage
        from app.models.report import Report, ReportConversation, ReportStateTracking, Evidence
        
        try:
            # Add timeout to fail fast if connection hangs (e.g. firewall/network issues)
            # 10 seconds should be plenty for a healthy connection
            async with asyncio.timeout(10):
                async with engine.begin() as conn:
                    # Check if at least one core table exists before running create_all
                    # This avoids overhead on every startup if DB is healthy
                    from sqlalchemy import inspect
                    
                    def check_tables(connection):
                        inspector = inspect(connection)
                        return inspector.has_table("beacon")
                    
                    if await conn.run_sync(check_tables):
                        logger.info("remote_db_already_initialized", message="Core tables found, skipping create_all")
                    else:
                        logger.info("remote_db_creating_tables", message="Tables missing, running create_all")
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
    asyncio.run(run_init_db())
