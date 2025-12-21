import asyncio
import json
import sys
import os

# Ensure we can import app code
sys.path.append(os.path.join(os.getcwd(), "backend"))

import logging
# Suppress all sqlalchemy logging
logging.getLogger("sqlalchemy.engine").setLevel(logging.ERROR)

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from app.core.config import settings
from app.models.beacon import Beacon
from sqlalchemy import select

# Create a local engine for clean output
engine = create_async_engine(str(settings.DATABASE_URL), echo=False)
AsyncSessionLocal = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

async def inspect_case(case_id: str):
    async with AsyncSessionLocal() as session:
        stmt = select(Beacon).where(Beacon.case_id == case_id)
        result = await session.execute(stmt)
        beacon = result.scalar_one_or_none()
        
        if not beacon:
            print(f"Case {case_id} not found.")
            return
            
        data = {
            "id": str(beacon.id),
            "reported_at": beacon.reported_at.isoformat() if beacon.reported_at else None,
            "case_id": beacon.case_id,
            "incident_summary": beacon.incident_summary,
            "credibility_score": beacon.credibility_score,
            "credibility_breakdown": beacon.credibility_breakdown,
            "authority_summary": beacon.authority_summary,
            "analysis_status": beacon.analysis_status,
            "evidence_files": beacon.evidence_files,
            "created_at": beacon.created_at.isoformat() if beacon.created_at else None,
            "updated_at": beacon.updated_at.isoformat() if beacon.updated_at else None
        }
        print(json.dumps(data, indent=2))

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python inspect_case.py <case_id>")
    else:
        asyncio.run(inspect_case(sys.argv[1]))
