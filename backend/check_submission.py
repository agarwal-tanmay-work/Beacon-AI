
import asyncio
from sqlalchemy import select
from app.db.local_db import LocalAsyncSession, init_local_db
from app.models.local_models import LocalSession, LocalConversation
from app.db.session import get_db, AsyncSession
from app.models.beacon import Beacon

async def check_db():
    print("--- Local SQLite Sessions ---")
    async with LocalAsyncSession() as local_session:
        stmt = select(LocalSession).order_by(LocalSession.created_at.desc()).limit(5)
        result = await local_session.execute(stmt)
        sessions = result.scalars().all()
        for s in sessions:
            print(f"ID: {s.id}, Active: {s.is_active}, Submitted: {s.is_submitted}, CaseID: {s.case_id}")
            
    print("\n--- Supabase Beacon Table ---")
    # Need to get a session from generator
    from app.db.session import engine
    from sqlalchemy.ext.asyncio import AsyncSession as AsyncSessionType
    from sqlalchemy.orm import sessionmaker
    
    LocalSessionMaker = sessionmaker(engine, class_=AsyncSessionType, expire_on_commit=False)
    async with LocalSessionMaker() as sb_session:
        stmt = select(Beacon).order_by(Beacon.created_at.desc()).limit(5)
        result = await sb_session.execute(stmt)
        beacons = result.scalars().all()
        for b in beacons:
            print(f"CaseID: {b.case_id}, ReportedAt: {b.reported_at}, Summary: {b.incident_summary[:50] if b.incident_summary else 'None'}")

if __name__ == "__main__":
    asyncio.run(check_db())
