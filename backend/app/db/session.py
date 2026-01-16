from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.pool import NullPool
from app.core.config import settings

# Create Async Engine
# For Supabase/PostgreSQL with asyncpg, SSL is typically required
db_url = settings.DATABASE_URL
# Support both postgres:// and postgresql:// and ensure asyncpg driver is used
if db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql+asyncpg://", 1)
elif db_url.startswith("postgresql://"):
    db_url = db_url.replace("postgresql://", "postgresql+asyncpg://", 1)

import ssl
import socket
import dns.resolver
from urllib.parse import urlparse, urlunparse

# FORCE IPv4: Manually resolve hostname to IPv4 to bypass uvloop/system IPv6 issues
# This is critical on Render where IPv6 routing to Supabase can be flaky (Network is unreachable)
try:
    parsed = urlparse(db_url)
    hostname = parsed.hostname
    if hostname and not hostname.replace('.', '').isdigit(): # Don't resolve if already IP
        # Use dnspython to query DNS directly, bypassing flaky system/libc resolver (Errno -5)
        resolver = dns.resolver.Resolver()
        # Use Google DNS as fallback if system DNS server is unreachable/broken
        resolver.nameservers = ['8.8.8.8', '8.8.4.4'] 
        answers = resolver.resolve(hostname, 'A')
        ipv4_addr = answers[0].to_text()
        
        print(f"[NETWORK] Resolved {hostname} to {ipv4_addr} (via dnspython)", flush=True)
        # Replace hostname with IP in the URL
        new_netloc = parsed.netloc.replace(hostname, ipv4_addr)
        db_url = urlunparse(parsed._replace(netloc=new_netloc))
except Exception as e:
    print(f"[NETWORK] Failed to resolve hostname: {e}", flush=True)

# Configure connection args
connect_args = {}

# Ensure SSL is enabled for Supabase/Public DBs
if "supabase" in db_url or "db." in db_url or "127.0.0.1" not in db_url: # Assume remote if not local
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
