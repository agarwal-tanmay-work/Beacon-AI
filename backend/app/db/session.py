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
from urllib.parse import urlparse, urlunparse, parse_qsl, urlencode

# FORCE IPv4: Manually resolve hostname to IPv4 to bypass uvloop/system IPv6 issues
# This is critical on Render where IPv6 routing to Supabase can be flaky (Network is unreachable)
try:
    parsed = urlparse(db_url)
    
    # [FIX] STRIP `sslmode` from query params!
    # asyncpg does not support `sslmode` in the connection string and raises "unexpected keyword argument".
    # We handle SSL manually via the `connect_args["ssl"]` below.
    qs = dict(parse_qsl(parsed.query))
    if "sslmode" in qs:
        del qs["sslmode"]
        new_query = urlencode(qs)
        parsed = parsed._replace(query=new_query)
        db_url = urlunparse(parsed)

    hostname = parsed.hostname
    if hostname and not hostname.replace('.', '').isdigit() and ":" not in hostname: # Don't resolve if already IP
        # Use dnspython to query DNS directly, bypassing flaky system/libc resolver (Errno -5)
        resolver = dns.resolver.Resolver()
        # Use Google DNS as fallback if system DNS server is unreachable/broken
        resolver.nameservers = ['8.8.8.8', '8.8.4.4'] 
        
        try:
            print(f"[NETWORK] Resolving {hostname} (IPv4/A)...", flush=True)
            answers = resolver.resolve(hostname, 'A')
            ipv4_addr = answers[0].to_text()
            print(f"[NETWORK] Resolved {hostname} to {ipv4_addr} (via dnspython)", flush=True)
            new_netloc = parsed.netloc.replace(hostname, ipv4_addr)
            db_url = urlunparse(parsed._replace(netloc=new_netloc))
        except Exception as e_a:
            print(f"[NETWORK] IPv4 resolution failed for {hostname}: {e_a}", flush=True)
            try:
                print(f"[NETWORK] Resolving {hostname} (IPv6/AAAA)...", flush=True)
                answers = resolver.resolve(hostname, 'AAAA')
                ipv6_addr = answers[0].to_text()
                print(f"[NETWORK] Resolved {hostname} to [{ipv6_addr}] (via dnspython)", flush=True)
                new_netloc = parsed.netloc.replace(hostname, f"[{ipv6_addr}]")
                db_url = urlunparse(parsed._replace(netloc=new_netloc))
            except Exception as e_aaaa:
                print(f"[NETWORK] IPv6 resolution also failed for {hostname}: {e_aaaa}", flush=True)
                print(f"[NETWORK] Falling back to system resolver for {hostname}", flush=True)
except Exception as e:
    print(f"[NETWORK] DNS helper logic errored: {e}", flush=True)

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

# If using Supabase Transaction Pooler (port 6543 OR explicit pooler hostname), we must disable prepared statements
# (Though we are currently on 5432, we keep this logic just in case)
if ":6543" in db_url or "pooler.supabase.com" in db_url:
    connect_args["statement_cache_size"] = 0

engine = create_async_engine(
    db_url,
    echo=settings.ENVIRONMENT == "development",
    future=True,
    pool_size=5,          # Supabase free tier: ~10 total connections; leave headroom for admin portal
    max_overflow=10,      # Burst cap: 15 total connections maximum
    pool_timeout=30,      # Raise TimeoutError instead of hanging if pool exhausted
    pool_recycle=1800,    # Recycle connections every 30 min to avoid stale sockets
    pool_pre_ping=True,   # Test connection health before checkout to handle dropped idle sockets
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
