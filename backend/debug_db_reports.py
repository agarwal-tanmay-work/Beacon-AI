import asyncio
from sqlalchemy import select
from app.db.session import async_session
from app.models.report import Report

async def list_reports():
    async with async_session() as db:
        result = await db.execute(select(Report.id, Report.case_id, Report.access_token_hash).limit(5))
        reports = result.all()
        print(f"Found {len(reports)} reports")
        for r in reports:
            print(f"ID: {r.id}, CaseID: {r.case_id}, TokenHash: {r.access_token_hash}")

if __name__ == "__main__":
    asyncio.run(list_reports())
