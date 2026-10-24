"""Schema management.

Alembic was configured but never usable (no revisions, and it needed a driver that is not installed), so
the real schema management has always been ``create_all``. That is kept, but done properly:

* ``create_all`` runs on every start (it only creates what is missing - the old "skip if the beacon table
  exists" shortcut meant tables added later were never created on an existing database);
* additive column changes are applied with ``ADD COLUMN IF NOT EXISTS`` (idempotent, never destructive).
"""

import asyncio

import structlog
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

import app.models  # noqa: F401  (registers the models)
from app.db.base import Base
from app.db.session import get_engine

logger = structlog.get_logger(__name__)

# Applied on PostgreSQL only; a fresh database gets these columns from create_all anyway.
_ADDITIVE_COLUMNS = ("ALTER TABLE beacon ADD COLUMN IF NOT EXISTS reporter_details JSON",)


async def ensure_schema(engine: AsyncEngine | None = None, *, timeout: float = 30.0) -> None:
    engine = engine or get_engine()
    async with asyncio.timeout(timeout):
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
            if conn.dialect.name == "postgresql":
                for statement in _ADDITIVE_COLUMNS:
                    await conn.execute(text(statement))
    logger.info("db_schema_ready", dialect=engine.dialect.name)
