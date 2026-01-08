import asyncio
import json
from app.db.local_db import LocalAsyncSession
from app.models.local_models import LocalStateTracking
from sqlalchemy import select

async def main():
    async with LocalAsyncSession() as session:
        stmt = select(LocalStateTracking).where(LocalStateTracking.session_id == '3c93b236-17d1-45ff-846d-e96fa66bb856')
        result = await session.execute(stmt)
        row = result.scalar_one_or_none()
        if row:
            print(json.dumps(row.context_data, indent=2))
        else:
            print("Session not found")

if __name__ == "__main__":
    asyncio.run(main())
