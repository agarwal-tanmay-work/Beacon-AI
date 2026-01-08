from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
import uuid
from datetime import datetime

from app.db.session import get_db
from app.models.beacon import Beacon
from app.schemas.report import CreateReportRequest, ReportResponse, MessageRequest, MessageResponse, ReportStatus, SenderType
from app.services.report_engine import ReportEngine

router = APIRouter()

@router.post("/create", response_model=ReportResponse)
async def create_report(
    request: CreateReportRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Initialize a new anonymous report session in the local staging database.
    """
    # Generate a unique session ID
    report_id = str(uuid.uuid4())
    # For now, we'll use a mocked token associated with the ID.
    access_token = f"tk_{uuid.uuid4().hex[:12]}"

    # Initialize report in local storage
    try:
        await ReportEngine.initialize_report(report_id, access_token)
    except Exception as e:
        error_msg = f"DB_ERROR: {str(e)[:200]}"
        raise HTTPException(status_code=500, detail=error_msg)
    
    # For now, we'll use a mocked token associated with the ID.
    access_token = f"tk_{uuid.uuid4().hex[:12]}"

    return ReportResponse(
        report_id=uuid.UUID(report_id),
        access_token=access_token,
        message="Secure session established. Speak freely, I am listening."
    )

@router.post("/message", response_model=MessageResponse)
async def handle_message(
    request: MessageRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
):
    """
    Handle incoming user message via the real ReportEngine/AI flow.
    """
    # Verify access token (Mocked for now)
    if not request.access_token.startswith("tk_"):
        raise HTTPException(status_code=401, detail="Invalid access token")

    try:
        # Process message via ReportEngine
        # This handles: Local history, LLM interaction, and Phase 1 Supabase INSERT on completion
        response = await ReportEngine.process_message(
            report_id=str(request.report_id),
            user_message=request.content,
            supabase_session=db,
            background_tasks=background_tasks
        )
        return response
    except Exception as e:
        import traceback
        error_msg = f"Error in handle_message: {str(e)}\n{traceback.format_exc()}"
        print(error_msg)
        raise HTTPException(status_code=500, detail=str(e))

