from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.pool import NullPool
from app.core.config import settings

# Create Async Engine
# For Supabase/PostgreSQL with asyncpg, SSL is specified in the URL, not connect_args
db_url = settings.DATABASE_URL
if db_url.startswith("postgresql://"):
     db_url = db_url.replace("postgresql://", "postgresql+asyncpg://", 1)

if "supabase" in db_url and "ssl=" not in db_url:
    # Add SSL requirement to URL for asyncpg
    db_url = db_url + ("&" if "?" in db_url else "?") + "ssl=require"

# Configure connection args
connect_args = {}
# If using Supabase Transaction Pooler (port 6543), we must disable prepared statements
if ":6543" in db_url:
    connect_args["statement_cache_size"] = 0

engine = create_async_engine(
    db_url,
    echo=settings.ENVIRONMENT == "development",
    future=True,
    poolclass=NullPool,
    connect_args=connect_args,
)

# Create Session Factory
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)

async def get_db() -> AsyncSession:
    """
    Dependency for getting an async database session.
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()
