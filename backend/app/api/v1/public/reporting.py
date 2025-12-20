from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.schemas.report import CreateReportRequest, ReportResponse, MessageRequest, MessageResponse
from app.models.report import Report, ReportStateTracking
from app.services.report_engine import ReportEngine
import secrets
import hashlib

router = APIRouter()

@router.post("/create", response_model=ReportResponse)
async def create_report(request: CreateReportRequest, db: AsyncSession = Depends(get_db)):
    """
    Start a new anonymous reporting session.
    Generates a secure access token for the user.
    """
    # Use client_seed for entropy mixing or just log it (Prototype: Log)
    # print(f"Init Report with Seed: {request.client_seed}")

    # Generate secure token
    raw_token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
    
    # Create Report
    new_report = Report(
        access_token_hash=token_hash
    )
    db.add(new_report)
    await db.flush() # Get ID
    
    # Initialize Engine State
    await ReportEngine.initialize_report(new_report.id, db)
    
    return ReportResponse(
        report_id=new_report.id,
        access_token=raw_token,
        message="Secure session established. Use this token for all future messages."
    )

@router.post("/message", response_model=MessageResponse)
async def send_message(request: MessageRequest, db: AsyncSession = Depends(get_db)):
    """
    Send a message to the reporting bot.
    Validated via Access Token.
    """
    # Validate Token
    input_hash = hashlib.sha256(request.access_token.encode()).hexdigest()
    # We should query strictly by ID and Hash to fetch the report
    # Optimization: In real prod, use Redis for session cache to avoid DB hit every msg
    # Here, we do direct DB for simplicity and strictness
    # (Actually we query ReportStateTracking joined with Report for efficiency? 
    #  For now, just verify report existence)
    
    # Check if report exists and matches token
    # (Skipping explicit query for Report object if we just blindly trust ID+Hash combination logic 
    #  but for security we must verify validity)
    # Let's trust the engine to fail if state not found, but we need to verify auth first.
    
    # Verify Auth
    # Ideally checking against the Report table
    # report = await db.scalar(select(Report).where(Report.id == request.report_id, Report.access_token_hash == input_hash))
    # For MVP speed, let's assume if the Engine finds the state, we rely on that? NO. MUST VERIFY TOKEN.
    
    from sqlalchemy import select
    stmt = select(Report).where(Report.id == request.report_id, Report.access_token_hash == input_hash)
    result = await db.execute(stmt)
    report = result.scalar_one_or_none()
    
    if not report:
        raise HTTPException(status_code=401, detail="Invalid credentials or session expired")
        
    if report.is_archived:
        raise HTTPException(status_code=400, detail="This report is closed.")

    # Process Message
    return await ReportEngine.process_message(request.report_id, request.content, db)
