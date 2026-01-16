"""
Local SQLite Database Configuration for Staging Data.

This database stores transient session data that authorities don't need:
- Active chat sessions
- Conversation messages
- State tracking
- Temporary evidence references

Data is transferred to Supabase beacon table only after case ID generation.
"""

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.pool import StaticPool
import os

# Local SQLite database path
LOCAL_DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "local_staging.db")
LOCAL_DB_URL = f"sqlite+aiosqlite:///{LOCAL_DB_PATH}"

# Create Async Engine for Local SQLite
local_engine = create_async_engine(
    LOCAL_DB_URL,
    echo=False,
    connect_args={
        "check_same_thread": False,
        "timeout": 30 # 30 second busy timeout
    }
)

# Enable WAL mode for better concurrency
from sqlalchemy import event

@event.listens_for(local_engine.sync_engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA synchronous=NORMAL")
    cursor.close()

# Create Session Factory for Local DB
LocalAsyncSession = async_sessionmaker(
    bind=local_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


async def get_local_db() -> AsyncSession:
    """
    Dependency for getting a local SQLite database session.
    """
    async with LocalAsyncSession() as session:
        try:
            yield session
        finally:
            await session.close()


async def init_local_db():
    """
    Initialize local SQLite database tables.
    """
    from app.models.local_models import LocalBase
    
    async with local_engine.begin() as conn:
        await conn.run_sync(LocalBase.metadata.create_all)
    
    print(f"[LOCAL_DB] Initialized local staging database at {LOCAL_DB_PATH}")
