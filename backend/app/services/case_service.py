"""Case ID allocation."""

import re

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.beacon import Beacon

CASE_ID_PATTERN = re.compile(r"^BCN\d{12}$")
_ADVISORY_LOCK_KEY = 7_302_026  # arbitrary, only has to be unique to this purpose within the database


class CaseService:
    PREFIX = "BCN"
    START = 100_000_000_001  # first ID ever issued: BCN100000000001

    @classmethod
    async def next_case_id(cls, session: AsyncSession) -> str:
        """Next sequential ID (``BCN`` + 12 digits).

        On PostgreSQL a transaction-scoped advisory lock serialises allocation across all workers/instances until
        the caller commits, so two simultaneous submissions can no longer pick the same number (the old
        read-max-then-insert approach relied on a unique-constraint violation plus a retry that also threw away the
        user's conversation messages).
        """
        bind = session.get_bind()
        if bind.dialect.name == "postgresql":
            await session.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": _ADVISORY_LOCK_KEY})

        # Same-length digit strings sort numerically, so the highest ID is the lexicographically largest well-formed one.
        rows = await session.execute(
            select(Beacon.case_id)
            .where(Beacon.case_id.like(f"{cls.PREFIX}%"), func.length(Beacon.case_id) == len(cls.PREFIX) + 12)
            .order_by(Beacon.case_id.desc())
            .limit(25)
        )
        for (case_id,) in rows:
            if CASE_ID_PATTERN.match(case_id):  # skips hand-made rows such as "BCNTEST000001"
                return f"{cls.PREFIX}{int(case_id[len(cls.PREFIX) :]) + 1}"
        return f"{cls.PREFIX}{cls.START}"
