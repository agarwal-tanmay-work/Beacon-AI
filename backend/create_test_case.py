import asyncio
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import engine
from app.models.beacon import Beacon
from datetime import datetime
import uuid

async def create_test_case():
    async with AsyncSession(engine) as session:
        case = Beacon(
            id=uuid.uuid4(),
            case_id="BCNTEST0000001",
            secret_key="TEST-KEY-01",
            status="Received",
            reported_at=datetime.utcnow(),
            incident_summary="This is a test incident for verifying tracking functionality.",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        session.add(case)
        await session.commit()
        print(f"Created Test Case - ID: {case.case_id}, Key: {case.secret_key}")

if __name__ == "__main__":
    asyncio.run(create_test_case())
