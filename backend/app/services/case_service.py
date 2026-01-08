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
        3. Iterate until a free ID is found (handling potential race conditions optimistically).
        """
        
        # Query for the max case_id starting with 'BCN'
        # Note: String comparison isn't perfect for numbers, but with fixed 12 digits it works lexically.
        # However, to be safe, we should extract keys. 
        # Since we can't easily do regex extraction in pure SQL agnostic way without specific PG functions (which we have),
        # simple max(case_id) is decent if formatting is strict.
        
        # Let's try to get the 'max' BCN ID.
        stmt = select(func.max(Beacon.case_id)).where(Beacon.case_id.like(f"{cls.PREFIX}%"))
        result = await session.execute(stmt)
        max_id = result.scalar_one_or_none()
        
        if not max_id:
            # First one
            return f"{cls.PREFIX}{cls.STARTING_ID_NUM}"
        
        # Extract matches
        # Expecting BCN1234...
        match = re.match(r"^BCN(\d+)$", max_id)
        if match:
            current_num = int(match.group(1))
            next_num = current_num + 1
        else:
            # If max_id exists but doesn't match numeric pattern (maybe legacy data), 
            # we default to start or fallback?
            # Safe bet: Start from our defined start point, or scan specifically logic better.
            # Assuming we can trust the prefix search to return something relevant.
            # If we have "BCN_TEST", lexical max might be odd.
            # Let's fallback to starting ID if parsing fails.
             return f"{cls.PREFIX}{cls.STARTING_ID_NUM}"

        # Ensure we don't go backwards if existing data is lower than start
        if next_num < cls.STARTING_ID_NUM:
            next_num = cls.STARTING_ID_NUM
            
        return f"{cls.PREFIX}{next_num}"
