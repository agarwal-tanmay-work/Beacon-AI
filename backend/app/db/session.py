from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.pool import NullPool
from app.core.config import settings

# Create Async Engine
# For Supabase/PostgreSQL with asyncpg, SSL is typically required
db_url = settings.DATABASE_URL
# Support both postgres:// and postgresql:// and ensure asyncpg driver is used
if db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql+asyncpg://", 1)
import ssl

# Configure connection args
connect_args = {}

# Ensure SSL is enabled for Supabase/Public DBs
if "supabase" in db_url or "db." in db_url:
    # asyncpg requires an actual SSLContext object, not just a string
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE  # For simple 'require' behavior, or CERT_REQUIRED if we have robust CA certs
    # Given we installed ca-certificates, we can try CERT_REQUIRED, but CERT_NONE is safer against random issuer errors
    # to behave like 'sslmode=require' without 'verify-full'.
    connect_args["ssl"] = ctx

# If using Supabase Transaction Pooler (port 6543), we must disable prepared statements
# (Though we are currently on 5432, we keep this logic just in case)
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
