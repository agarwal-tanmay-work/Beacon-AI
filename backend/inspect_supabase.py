import asyncio
from app.db.session import get_db
from app.models.beacon import Beacon
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import json

async def main():
    async for db in get_db():
        # Get the most recent report
        stmt = select(Beacon).order_by(Beacon.created_at.desc()).limit(1)
        result = await db.execute(stmt)
        beacon = result.scalar_one_or_none()
        
        if beacon:
            print("=== LATEST BEACON ENTRY ===")
            data = {
                "case_id": beacon.case_id,
                "reported_at": str(beacon.reported_at),
                "analysis_status": beacon.analysis_status,
                "analysis_attempts": beacon.analysis_attempts,
                "analysis_last_error": beacon.analysis_last_error,
                "incident_summary": beacon.incident_summary,
                "credibility_score": beacon.credibility_score,
                "credibility_breakdown": beacon.credibility_breakdown,
                "authority_summary": (beacon.authority_summary[:500] + "...") if beacon.authority_summary else None,
                "evidence_count": len(beacon.evidence_files) if beacon.evidence_files else 0
            }
            print(json.dumps(data, indent=2))
        else:
            print("No reports found in beacon table.")
        break

if __name__ == "__main__":
    asyncio.run(main())
