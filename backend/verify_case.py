import asyncio
import sys
import os
import json

# Add the current directory to sys.path to allow importing 'app'
sys.path.append(os.getcwd())

from app.db.session import AsyncSessionLocal
from app.models.beacon import Beacon
from sqlalchemy import select

async def verify_supabase(case_id):
    print(f"Verifying Case ID {case_id} in Supabase...")
    async with AsyncSessionLocal() as session:
        stmt = select(Beacon).where(Beacon.case_id == case_id)
        result = await session.execute(stmt)
        beacon = result.scalar_one_or_none()
        
        if not beacon:
            print(f"❌ Error: Case {case_id} not found in Supabase 'beacon' table.")
            return
        
        print(f"✅ Case found in Supabase.")
        print(f"   Status: {beacon.analysis_status}")
        print(f"   Reported At: {beacon.reported_at}")
        print(f"   Score: {beacon.credibility_score}")
        print(f"   Evidence: {json.dumps(beacon.evidence_files, indent=2)}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: py verify_case.py <case_id>")
        sys.exit(1)
    
    case_id = sys.argv[1]
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(verify_supabase(case_id))
