from typing import Any, List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from sqlalchemy.orm import selectinload

from app.db.session import get_db
from app.api import deps
from app.models.report import Report, ReportStateTracking
from app.models.admin import Admin

router = APIRouter()

# Schema for List View (Simplified)
from pydantic import BaseModel, UUID4, Field
from datetime import datetime
from app.models.report import ReportStatus, ReportPriority

class ReportListItem(BaseModel):
    id: UUID4
    status: ReportStatus
    priority: ReportPriority
    credibility_score: int | None
    created_at: datetime
    # No PII here

class ReportDetail(BaseModel):
    id: UUID4
    status: ReportStatus
    priority: ReportPriority
    credibility_score: int | None
    score_explanation: str | None
    categories: list
    location_meta: dict | None
    created_at: datetime
    # We include redacted conversations
    conversations: List[dict] # Simplified for now
    evidence: List[dict] 

@router.get("/", response_model=List[ReportListItem])
async def read_reports(
    db: AsyncSession = Depends(get_db),
    skip: int = 0,
    limit: int = 100,
    current_admin: Admin = Depends(deps.get_current_admin),
) -> Any:
    """
    Retrieve reports.
    """
    stmt = select(Report).order_by(desc(Report.created_at)).offset(skip).limit(limit)
    result = await db.execute(stmt)
    reports = result.scalars().all()
    return reports

@router.get("/{report_id}", response_model=ReportDetail)
async def read_report_by_id(
    report_id: UUID4,
    db: AsyncSession = Depends(get_db),
    current_admin: Admin = Depends(deps.get_current_admin),
) -> Any:
    """
    Get a specific report by id with details.
    """
    # Eager load related data
    stmt = select(Report).options(
        selectinload(Report.conversations),
        selectinload(Report.evidence)
    ).where(Report.id == report_id)
    
    result = await db.execute(stmt)
    report = result.scalar_one_or_none()
    
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
        
    return report

@router.put("/{report_id}/status")
async def update_report_status(
    report_id: UUID4,
    status: ReportStatus,
    db: AsyncSession = Depends(get_db),
    current_admin: Admin = Depends(deps.get_current_admin),
):
    """
    Update report status.
    """
    stmt = select(Report).where(Report.id == report_id)
    result = await db.execute(stmt)
    report = result.scalar_one_or_none()
    
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    
    report.status = status
    await db.commit()
    return {"status": "updated", "new_status": status}
