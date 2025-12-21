"""
Public Reporting API.

Uses LOCAL SQLite for session management.
Beacon table INSERT only happens when case is submitted.
"""

from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.db.session import get_db
from app.db.local_db import LocalAsyncSession
from app.models.local_models import LocalSession, LocalStateTracking
from app.models.beacon import Beacon
from app.schemas.report import CreateReportRequest, ReportResponse, MessageRequest, MessageResponse
from app.services.report_engine import ReportEngine
import secrets
import hashlib
import uuid as uuid_module
from datetime import datetime

router = APIRouter()


@router.post("/create", response_model=ReportResponse)
async def create_report(request: CreateReportRequest, db: AsyncSession = Depends(get_db)):
    """
    Start a new anonymous reporting session.
    Stores session in LOCAL SQLite (not Supabase yet).
    Generates a secure access token for the user.
    """
    import traceback
    try:
        # Generate secure token
        raw_token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
        
        # Generate a new session ID (UUID format for compatibility)
        session_uuid = uuid_module.uuid4()
        session_id = str(session_uuid)
        
        # Create session in LOCAL SQLite
        async with LocalAsyncSession() as local_session:
            new_session = LocalSession(
                id=session_id,
                access_token_hash=token_hash
            )
            local_session.add(new_session)
            
            # Initialize state tracking in same session
            state_tracking = LocalStateTracking(
                session_id=session_id,
                current_step="ACTIVE",
                context_data={
                    "initialized_at": str(uuid_module.uuid1().time),
                    "extracted": {}
                }
            )
            local_session.add(state_tracking)
            
            await local_session.commit()
            print(f"[CREATE_REPORT] Created session: {session_id}")
        
        return ReportResponse(
            report_id=session_uuid,  # Return as UUID
            access_token=raw_token,
            message="Secure session established. Use this token for all future messages."
        )
    except Exception as e:
        print(f"[CREATE_REPORT ERROR] {type(e).__name__}: {e}")
        traceback.print_exc()
        raise


@router.post("/message", response_model=MessageResponse)
async def send_message(
    request: MessageRequest, 
    background_tasks: BackgroundTasks, 
    db: AsyncSession = Depends(get_db)
):
    """
    Send a message to the reporting bot.
    Validated via Access Token against LOCAL SQLite.
    """
    import traceback
    
    # Convert UUID to string for local DB lookup
    session_id = str(request.report_id)
    
    # Validate Token against LOCAL DB
    input_hash = hashlib.sha256(request.access_token.encode()).hexdigest()
    
    async with LocalAsyncSession() as local_session:
        try:
            stmt = select(LocalSession).where(
                LocalSession.id == session_id, 
                LocalSession.access_token_hash == input_hash
            )
            result = await local_session.execute(stmt)
            session = result.scalar_one_or_none()
        except Exception as e:
            print(f"[AUTH ERROR] {type(e).__name__}: {e}")
            traceback.print_exc()
            raise HTTPException(status_code=500, detail="Database error during authentication")
        
        if not session:
            print(f"[AUTH ERROR] Session not found for id={session_id}, hash={input_hash[:16]}...")
            raise HTTPException(status_code=401, detail="Invalid credentials or session expired")
        
        if not session.is_active:
            raise HTTPException(status_code=400, detail="This session is closed.")
        
        if session.is_submitted:
            # Instead of rejecting, gracefully return the Case ID the user missed
            from app.models.report import SenderType
            from uuid import UUID as UUIDType
            return MessageResponse(
                report_id=UUIDType(session_id),
                sender=SenderType.SYSTEM,
                content=f"Your report has already been submitted. Your Case ID is: **{session.case_id}**. Please save this ID to track your case.",
                timestamp=datetime.utcnow(),
                next_step="SUBMITTED",
                case_id=session.case_id
            )
    
    # Process Message (uses both local and Supabase sessions)
    return await ReportEngine.process_message(
        session_id,  # Pass as string
        request.content, 
        db, 
        background_tasks
    )


@router.get("/status/{session_id}")
async def get_session_status(session_id: str):
    """
    Get session status from local database.
    """
    status = await ReportEngine.get_session_status(session_id)
    if "error" in status:
        raise HTTPException(status_code=404, detail=status["error"])
    return status


@router.get("/case/{case_id}")
async def get_case_info(case_id: str, db: AsyncSession = Depends(get_db)):
    """
    Get case information from Supabase beacon table.
    Only returns cases that have been submitted.
    """
    # Validate case_id format
    if not Beacon.validate_case_id(case_id):
        raise HTTPException(status_code=400, detail="Invalid case ID format. Expected: BCN + 12 digits")
    
    stmt = select(Beacon).where(Beacon.case_id == case_id)
    result = await db.execute(stmt)
    beacon = result.scalar_one_or_none()
    
    if not beacon:
        raise HTTPException(status_code=404, detail="Case not found")
    
    return {
        "case_id": beacon.case_id,
        "reported_at": beacon.reported_at.isoformat() if beacon.reported_at else None,
        "incident_summary": beacon.incident_summary,
        "credibility_score": beacon.credibility_score,
        "authority_summary": beacon.authority_summary,
        "evidence_count": len(beacon.evidence_files) if beacon.evidence_files else 0,
        "created_at": beacon.created_at.isoformat() if beacon.created_at else None,
        "updated_at": beacon.updated_at.isoformat() if beacon.updated_at else None
    }
