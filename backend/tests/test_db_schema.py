import asyncio
import sys
import os

# Add backend directory to path
sys.path.append(os.path.abspath("backend"))

from app.db.session import SessionLocal
from app.models.report import Report
from sqlalchemy import select

async def test_db():
    try:
        async with SessionLocal() as session:
            stmt = select(Report).limit(1)
            result = await session.execute(stmt)
            report = result.scalar_one_or_none()
            print("DB Connection OK")
            if report:
                print(f"Report ID: {report.id}")
                # Use hasattr to check for column in model instance
                if hasattr(report, 'case_id'):
                    print(f"Case ID column exists in model: {report.case_id}")
                else:
                    print("Case ID column NOT in model")
            else:
                print("No reports found.")
    except Exception as e:
        print(f"General DB Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_db())
