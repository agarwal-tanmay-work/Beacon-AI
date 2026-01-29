import asyncio
import uuid
from datetime import datetime, timezone
from sqlalchemy import select
from app.db.session import AsyncSessionLocal
from app.models.beacon import Beacon

async def verify_null_score():
    print("Starting verification: Inserting Beacon with NULL credibility_score...")
    async with AsyncSessionLocal() as session:
        try:
            case_id = f"BCNTEST{uuid.uuid4().hex[:7].upper()}"
            new_case = Beacon(
                case_id=case_id,
                reported_at=datetime.now(timezone.utc),
                secret_key="TEST-KEY",
                secret_key_hash="TEST-HASH",
                status="Received",
                incident_summary="Test summary for verification of NULL score insertion.",
                evidence_files=[],
                analysis_status="pending",
                credibility_score=None,
                credibility_breakdown=None
            )
            session.add(new_case)
            await session.commit()
            print(f"Successfully inserted Beacon {case_id} with NULL score.")
            
            # Verify it's actually NULL in the DB
            stmt = select(Beacon).where(Beacon.case_id == case_id)
            result = await session.execute(stmt)
            fetched_case = result.scalar_one_or_none()
            print(f"Fetched score: {fetched_case.credibility_score} (Expected: None)")
            
            # Clean up
            await session.delete(fetched_case)
            await session.commit()
            print("Cleanup successful.")
            
        except Exception as e:
            print(f"Verification FAILED: {e}")
            await session.rollback()
            raise

if __name__ == "__main__":
    asyncio.run(verify_null_score())
