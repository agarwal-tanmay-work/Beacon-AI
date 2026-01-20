
import asyncio
from sqlalchemy import select, func
from app.db.session import AsyncSessionLocal
from app.models.beacon import Beacon
from app.models.report import Report

async def check_counts():
    async with AsyncSessionLocal() as session:
        print("Checking Beacon table count...")
        try:
            result = await session.execute(select(func.count()).select_from(Beacon))
            beacon_count = result.scalar()
            print(f"Beacon Count: {beacon_count}")
        except Exception as e:
            print(f"Error checking Beacon: {e}")

        print("Checking Report table count...")
        try:
            result = await session.execute(select(func.count()).select_from(Report))
            report_count = result.scalar()
            print(f"Report Count: {report_count}")
        except Exception as e:
            print(f"Error checking Report: {e}")

if __name__ == "__main__":
    asyncio.run(check_counts())
