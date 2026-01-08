from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from typing import List
import uuid

from app.db.session import get_db
from app.models.beacon import Beacon
# We need a schema that matches what the frontend expects.
# The frontend Interface Report has: id, status, priority, credibility_score, created_at
from pydantic import BaseModel
from datetime import datetime

router = APIRouter()

class AdminReportSchema(BaseModel):
    id: uuid.UUID
    status: str
    priority: str
    credibility_score: int
    created_at: datetime
    case_id: str

    class Config:
        from_attributes = True

@router.get("/", response_model=List[AdminReportSchema])
async def get_reports(
    db: AsyncSession = Depends(get_db)
):
    """
    Fetch all reports for the admin dashboard.
    """
    query = select(Beacon).order_by(desc(Beacon.reported_at))
    result = await db.execute(query)
    beacons = result.scalars().all()
    
    # Map Beacon model to AdminReportSchema
    # Note: Beacon model doesn't have 'status' or 'priority' fields matching the frontend exactly 
    # (it has analysis_status). We will map them.
    
    reports_data = []
    for b in beacons:
        # Map analysis_status to ReportStatus
        status = "NEW"
        if b.analysis_status == "completed":
            status = "VERIFIED"
        
        # Mock priority based on score
        priority = "MEDIUM"
        if b.credibility_score and b.credibility_score > 80:
            priority = "HIGH"
        if b.credibility_score and b.credibility_score > 90:
            priority = "CRITICAL"

        reports_data.append(AdminReportSchema(
            id=b.id,
            status=status,
            priority=priority,
            credibility_score=b.credibility_score or 0,
            created_at=b.reported_at,
            case_id=b.case_id
        ))

    return reports_data
