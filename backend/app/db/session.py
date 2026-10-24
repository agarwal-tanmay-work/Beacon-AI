"""Async engine / session management.

The engine is created lazily (first use), not at import time: the old module resolved DNS and opened
SSL contexts while merely being imported, which made start-up order fragile and tests impossible.
"""

import ipaddress
import socket
import ssl
import uuid
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import structlog
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings

logger = structlog.get_logger(__name__)

_LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}


@dataclass
class EngineConfig:
    url: str
    connect_args: dict[str, Any] = field(default_factory=dict)
    is_sqlite: bool = False
    transaction_pooler: bool = False


def resolve_ipv4(host: str) -> str | None:
    """Resolve ``host`` to an IPv4 address (Render cannot reach Supabase's IPv6-only hosts).

    The system resolver is tried first; if it is flaky (``Errno -5`` on Render) public DNS via
    dnspython is used as a fallback.
    """
    try:
        infos = socket.getaddrinfo(host, None, family=socket.AF_INET, type=socket.SOCK_STREAM)
        if infos:
            return str(infos[0][4][0])
    except OSError as exc:
        logger.warning("db_dns_system_resolver_failed", host=host, error=str(exc))
    try:
        import dns.resolver

        resolver = dns.resolver.Resolver()
        resolver.nameservers = ["8.8.8.8", "1.1.1.1"]
        resolver.lifetime = 5.0
        return str(resolver.resolve(host, "A")[0])
    except Exception as exc:  # noqa: BLE001 - any DNS failure just means "keep the hostname"
        logger.warning("db_dns_fallback_failed", host=host, error=type(exc).__name__)
        return None


def prepare_engine_config(raw_url: str, *, resolver: Callable[[str], str | None] = resolve_ipv4) -> EngineConfig:
    """Turn the configured DATABASE_URL into an asyncpg-ready URL plus connect arguments."""
    url = raw_url.strip()
    for legacy in ("postgres://", "postgresql://", "postgresql+psycopg2://", "postgresql+psycopg://"):
        if url.startswith(legacy):
            url = "postgresql+asyncpg://" + url[len(legacy) :]
            break
    if url.startswith("sqlite"):
        return EngineConfig(url=url, is_sqlite=True)

    parts = urlsplit(url)
    query = dict(parse_qsl(parts.query, keep_blank_values=True))
    # asyncpg rejects libpq-style "sslmode" in the DSN; translate it into connect_args instead.
    requested = (query.pop("sslmode", None) or query.pop("ssl", None) or "").lower()
    hostname = parts.hostname or ""
    is_local = hostname in _LOCAL_HOSTS or not hostname

    mode = settings.DB_SSL_MODE
    if mode == "auto":
        if is_local or requested == "disable":
            mode = "disable"
        elif requested in ("verify-full", "verify-ca"):
            mode = "verify-full"
        else:
            mode = "require"

    connect_args: dict[str, Any] = {}
    if mode == "disable":
        connect_args["ssl"] = False
    elif mode == "require":
        connect_args["ssl"] = "require"  # encrypted, certificate not verified (Supabase pooler default)
    else:  # verify-full
        connect_args["ssl"] = ssl.create_default_context(cafile=settings.DB_SSL_CA_FILE)

    transaction_pooler = parts.port == 6543 or "pooler.supabase.com" in hostname
    if transaction_pooler:
        # pgbouncer / Supavisor transaction mode cannot reuse named prepared statements
        # (harmless, if slightly slower, on the session pooler too).
        query["prepared_statement_cache_size"] = "0"
        connect_args["statement_cache_size"] = 0
        connect_args["prepared_statement_name_func"] = lambda: f"__asyncpg_{uuid.uuid4()}__"

    netloc = parts.netloc
    if settings.DB_FORCE_IPV4 and not is_local and mode != "verify-full":
        try:
            ipaddress.ip_address(hostname)
        except ValueError:
            address = resolver(hostname)
            if address:
                userinfo, _, hostport = parts.netloc.rpartition("@")
                port = f":{parts.port}" if parts.port else ""
                netloc = f"{userinfo + '@' if userinfo else ''}{address}{port}"
                logger.info("db_host_pinned_to_ipv4", host=hostname, address=address)
            else:
                logger.warning("db_host_not_pinned", host=hostname)

    final = urlunsplit((parts.scheme, netloc, parts.path, urlencode(query), parts.fragment))
    return EngineConfig(url=final, connect_args=connect_args, transaction_pooler=transaction_pooler)


_engine: AsyncEngine | None = None
_sessionmaker: async_sessionmaker[AsyncSession] | None = None


def get_engine() -> AsyncEngine:
    global _engine, _sessionmaker
    if _engine is None:
        config = prepare_engine_config(settings.DATABASE_URL)
        kwargs: dict[str, Any] = {"connect_args": config.connect_args, "echo": False}
        if not config.is_sqlite:
            kwargs.update(
                pool_size=settings.DB_POOL_SIZE,
                max_overflow=settings.DB_MAX_OVERFLOW,
                pool_timeout=30,  # fail with a clear error instead of hanging when the pool is exhausted
                pool_recycle=1800,  # avoid stale sockets
                pool_pre_ping=True,
            )
        _engine = create_async_engine(config.url, **kwargs)
        _sessionmaker = async_sessionmaker(_engine, expire_on_commit=False, autoflush=False)
    return _engine


def get_sessionmaker() -> async_sessionmaker[AsyncSession]:
    get_engine()
    assert _sessionmaker is not None
    return _sessionmaker


async def dispose_engine() -> None:
    global _engine, _sessionmaker
    if _engine is not None:
        await _engine.dispose()
    _engine, _sessionmaker = None, None


def use_engine(engine: AsyncEngine) -> None:
    """Inject an already-built engine (tests)."""
    global _engine, _sessionmaker
    _engine = engine
    _sessionmaker = async_sessionmaker(engine, expire_on_commit=False, autoflush=False)


@asynccontextmanager
async def open_session() -> AsyncIterator[AsyncSession]:
    """For code that runs outside a request (background tasks, start-up work)."""
    async with get_sessionmaker()() as session:
        yield session


async def get_db() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency. Work is only persisted when the endpoint commits explicitly."""
    async with get_sessionmaker()() as session:
        yield session
