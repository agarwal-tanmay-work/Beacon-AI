from sqlalchemy import select, func, text
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.beacon import Beacon
import structlog
import re

logger = structlog.get_logger()

class CaseService:
    """
    Service for Case specific logic, primarily ID generation.
    """
    
    PREFIX = "BCN"
    DIGITS = 12
    STARTING_ID_NUM = 100000000001 # As requested: BCN100000000001
    
    @classmethod
    async def generate_next_case_id(cls, session: AsyncSession) -> str:
        """
        Generates the next incremental Case ID.
        Format: BCN + 12 digits (e.g. BCN100000000001).
        
        Logic:
        1. Find the maximum existing Case ID that matches the pattern BCN + digits.
        2. Extract numbers, increment by 1.
        3. Iterate until a free ID is found (guaranteeing uniqueness).
        """
        
        # Use PostgreSQL regex to find only numeric Case IDs that match the prefix
        # This prevents non-numeric IDs (like BCNTEST) from interfering with the counter.
        # '~' is the PostgreSQL operator for POSIX regular expressions.
        stmt = select(Beacon.case_id).where(
            Beacon.case_id.like(f"{cls.PREFIX}%"),
            Beacon.case_id.op("~")(f"^{cls.PREFIX}\\d+$")
        ).order_by(text("SUBSTRING(case_id, 4)::BIGINT DESC")).limit(1)
        
        result = await session.execute(stmt)
        max_id = result.scalar_one_or_none()
        
        if not max_id:
            next_num = cls.STARTING_ID_NUM
        else:
            match = re.match(r"^BCN(\d+)$", max_id)
            if match:
                next_num = int(match.group(1)) + 1
            else:
                next_num = cls.STARTING_ID_NUM

        if next_num < cls.STARTING_ID_NUM:
            next_num = cls.STARTING_ID_NUM
            
        # Uniqueness Guarantee Loop
        while True:
            case_id = f"{cls.PREFIX}{next_num}"
            existing_stmt = select(Beacon.case_id).where(Beacon.case_id == case_id)
            existing_res = await session.execute(existing_stmt)
            if not existing_res.scalar_one_or_none():
                return case_id
            next_num += 1

    @classmethod
    async def generate_unique_secret_key(cls, session: AsyncSession) -> str:
        """
        Generates a unique random Secret Key.
        Format: XXXX-XXXX (8 chars hex).
        """
        import secrets
        while True:
            # We use 4 bytes (8 hex chars) which provides 4.2 billion combinations.
            # For 100% guarantee, we check existence in DB.
            raw_hex = secrets.token_hex(4).upper()
            secret_key = f"{raw_hex[:4]}-{raw_hex[4:]}"
            
            # Check for collision
            stmt = select(Beacon.case_id).where(Beacon.secret_key == secret_key)
            result = await session.execute(stmt)
            if not result.scalar_one_or_none():
                return secret_key
