import asyncio
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import engine
from app.models.beacon import Beacon
from sqlalchemy import select

async def check_cases():
    async with AsyncSession(engine) as session:
        result = await session.execute(select(Beacon))
        cases = result.scalars().all()
        if not cases:
            print("No cases found in database.")
            return
        
        print(f"Found {len(cases)} cases:")
        for case in cases:
            print(f"- Case ID: {case.case_id}, Secret Key: {case.secret_key}")

if __name__ == "__main__":
    asyncio.run(check_cases())
