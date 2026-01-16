from fastapi import APIRouter, Depends, Body
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from typing import List
import uuid

from app.db.session import get_db
from app.models.beacon import Beacon
# We need a schema that matches what the frontend expects.
# The frontend Interface Report has: id, status, priority, credibility_score, created_at
from pydantic import BaseModel, validator
from datetime import datetime, timezone
from app.models.beacon_update import BeaconUpdate
from app.models.beacon_message import BeaconMessage
from app.schemas.report import TrackMessage, MessageAttachment, TrackMessageRequest, SecureUploadResponse
from fastapi import UploadFile, File, Form, HTTPException
import os
import hashlib
from typing import List, Optional, Any
from app.api.deps import get_current_admin

router = APIRouter(dependencies=[Depends(get_current_admin)])


class CaseUpdateSchema(BaseModel):
    id: str
    public_update: str
    created_at: Any
    updated_by: str

    @validator("created_at", pre=True)
    def ensure_utc(cls, v):
        if isinstance(v, datetime):
            if v.tzinfo is None: v = v.replace(tzinfo=timezone.utc)
            return v.astimezone(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
        return v

class AdminReportSchema(BaseModel):
    id: uuid.UUID
    status: str
    priority: str
    credibility_score: int
    created_at: Any
    case_id: str
    incident_summary: Optional[str] = None
    app_score_explanation: Optional[str] = None
    evidence_files: Optional[List[dict]] = []
    updates: Optional[List[CaseUpdateSchema]] = []
    
    @validator("created_at", pre=True)
    def ensure_utc(cls, v):
        if isinstance(v, datetime):
            if v.tzinfo is None: v = v.replace(tzinfo=timezone.utc)
            return v.astimezone(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
        return v

    class Config:
        from_attributes = True

class UpdateStatusRequest(BaseModel):
    status: str

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
    
    reports_data = []
    for b in beacons:
        # Status Logic
        raw_status = b.status
        if raw_status == "Received":
            status = "Pending"
        else:
            status = raw_status
        
        # Priority Logic
        score = b.credibility_score or 0
        if score >= 75:
            priority = "High"
        elif score >= 40:
            priority = "Medium"
        else:
            priority = "Low"

        # Evidence files handling
        evidence = []
        if b.evidence_files:
            # It's stored as JSON list of dicts
            evidence = b.evidence_files

        reports_data.append(AdminReportSchema(
            id=b.id,
            status=status,
            priority=priority,
            credibility_score=score,
            created_at=b.reported_at,
            case_id=b.case_id,
            incident_summary=b.incident_summary,
            app_score_explanation=b.score_explanation,
            evidence_files=evidence
        ))

    return reports_data

@router.get("/{id}", response_model=AdminReportSchema)
async def get_report_detail(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_db)
):
    """
    Fetch full detail for a single report.
    """
    case = await db.get(Beacon, id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    
    # Status Logic
    raw_status = case.status
    if raw_status == "Received":
        status = "Pending"
    else:
        status = raw_status
    
    # Priority Logic
    score = case.credibility_score or 0
    if score >= 75:
        priority = "High"
    elif score >= 40:
        priority = "Medium"
    else:
        priority = "Low"

    evidence = []
    if case.evidence_files:
        evidence = case.evidence_files

    # Fetch Updates
    updates_stmt = select(BeaconUpdate).where(
        BeaconUpdate.case_id == case.case_id
    ).order_by(BeaconUpdate.created_at.asc())
    updates_result = await db.execute(updates_stmt)
    updates_objs = updates_result.scalars().all()
    
    updates_data = []
    for u in updates_objs:
        updates_data.append({
            "id": str(u.id),
            "public_update": u.public_update,
            "created_at": u.created_at,
            "updated_by": "NGO" # Placeholder as model usually doesn't store this yet or not required for display
        })

    return AdminReportSchema(
        id=case.id,
        status=status,
        priority=priority,
        credibility_score=score,
        created_at=case.reported_at,
        case_id=case.case_id,
        incident_summary=case.incident_summary,
        app_score_explanation=case.score_explanation,
        evidence_files=evidence,
        updates=updates_data
    )

@router.put("/{id}/status", response_model=AdminReportSchema)
async def update_report_status(
    id: uuid.UUID,
    request: UpdateStatusRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Update the status of a report.
    Valid statuses: Pending, Ongoing, Completed
    """
    case = await db.get(Beacon, id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    
    valid_statuses = ["Pending", "Ongoing", "Completed"]
    if request.status not in valid_statuses:
        raise HTTPException(status_code=400, detail="Invalid status. Must be Pending, Ongoing, or Completed.")
    
    case.status = request.status
    # If explicitly setting to Pending, we store "Pending" (db default was "Received" but "Pending" is fine now)
    
    await db.commit()
    await db.refresh(case)
    
    # Return updated schema
    score = case.credibility_score or 0
    if score >= 75:
        priority = "High"
    elif score >= 40:
        priority = "Medium"
    else:
        priority = "Low"

    return AdminReportSchema(
        id=case.id,
        status=case.status,
        priority=priority,
        credibility_score=score,
        created_at=case.reported_at,
        case_id=case.case_id
    )

@router.get("/{id}/messages", response_model=List[TrackMessage])
async def get_case_messages(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_db)
):
    """
    Fetch all messages for a specific case by its UUID.
    """
    case = await db.get(Beacon, id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
        
    stmt = select(BeaconMessage).where(
        BeaconMessage.case_id == case.case_id
    ).order_by(BeaconMessage.created_at.asc())
    
    result = await db.execute(stmt)
    messages = result.scalars().all()
    
    return [
        TrackMessage(
            id=str(msg.id),
            sender_role=msg.sender_role,
            content=msg.content,
            attachments=[
                MessageAttachment(
                    file_name=att.get("file_name"),
                    file_path=att.get("file_path", "").replace("\\", "/"),
                    mime_type=att.get("mime_type")
                ) for att in (msg.attachments or [])
            ],
            timestamp=msg.created_at
        ) for msg in messages
    ]

@router.post("/{id}/message", response_model=TrackMessage)
async def admin_send_message(
    id: uuid.UUID,
    request: TrackMessageRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    NGO sends a message to the user.
    """
    case = await db.get(Beacon, id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
        
    new_message = BeaconMessage(
        case_id=case.case_id,
        sender_role="ngo",
        content=request.content,
        attachments=[att.model_dump() for att in request.attachments]
    )
    db.add(new_message)
    await db.commit()
    await db.refresh(new_message)
    
    return TrackMessage(
        id=str(new_message.id),
        sender_role=new_message.sender_role,
        content=new_message.content,
        attachments=[
            MessageAttachment(
                file_name=att.get("file_name"),
                file_path=att.get("file_path", "").replace("\\", "/"),
                mime_type=att.get("mime_type")
            ) for att in (new_message.attachments or [])
        ],
        timestamp=new_message.created_at
    )

@router.post("/{id}/upload", response_model=SecureUploadResponse)
async def upload_admin_file(
    id: uuid.UUID,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db)
):
    """
    Upload a file for the NGO communication channel.
    """
    case = await db.get(Beacon, id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
        
    try:
        from app.services.storage_service import StorageService
        from app.core.config import settings
        UPLOAD_DIR = "uploads"
        # SECURITY NOTE: In prod, use S3 or similar. Local storage for demo.
        if not os.path.exists(UPLOAD_DIR):
            os.makedirs(UPLOAD_DIR)
        
        content = await file.read()
        file_ext = os.path.splitext(file.filename)[1]
        unique_filename = f"{uuid.uuid4()}{file_ext}"
        file_path = ""

        # Production Upload
        if settings.SUPABASE_URL and settings.SUPABASE_KEY and settings.ENVIRONMENT != "local_dev":
            try:
                upload_res = await StorageService.upload_file(content, file.filename, file.content_type or "application/octet-stream")
                file_path = f"supastorage://{upload_res['bucket']}/{upload_res['path']}"
            except Exception as e:
                # Log and fallback to local
                print(f"[ADMIN_UPLOAD] Supabase upload failed: {e}")
        
        if not file_path:
            local_path = os.path.join(UPLOAD_DIR, unique_filename).replace("\\", "/")
            with open(local_path, "wb") as f:
                f.write(content)
            file_path = local_path
            
        return SecureUploadResponse(
            file_name=file.filename,
            file_path=file_path,
            mime_type=file.content_type or "application/octet-stream"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to upload file: {str(e)}")
