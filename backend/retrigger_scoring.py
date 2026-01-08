import asyncio
from app.db.session import AsyncSessionLocal
from app.db.local_db import LocalAsyncSession
from app.models.beacon import Beacon
from app.models.local_models import LocalSession
from sqlalchemy import select
from app.services.scoring_service import ScoringService

async def main():
    async with AsyncSessionLocal() as db:
        # Get latest beacon
        stmt = select(Beacon).order_by(Beacon.created_at.desc()).limit(1)
        res = await db.execute(stmt)
        beacon = res.scalar_one_or_none()
        
        if not beacon:
            print("No beacon found.")
            return
            
        case_id = beacon.case_id
        
        # We need the original session_id (which is in local_sessions)
        async with LocalAsyncSession() as local_db:
            stmt = select(LocalSession).where(LocalSession.case_id == case_id)
            res = await local_db.execute(stmt)
            local_sess = res.scalar_one_or_none()
            
            if not local_sess:
                print(f"Original session for {case_id} not found.")
                return
                
            session_id = local_sess.id
            print(f"Re-triggering scoring for Case: {case_id}, Session: {session_id}")
            
            await ScoringService.run_background_scoring(session_id, case_id)
            print("Re-scoring attempt finished.")

if __name__ == "__main__":
    asyncio.run(main())
