"""
Report Engine - Backend Observer Pattern with Two-Tier Database.

Data Flow:
1. Chat sessions stored in LOCAL SQLite (transient)
2. Final case data stored in SUPABASE beacon table (permanent)

Key Rules:
- ONE row per case in beacon table (INSERT once, UPDATE after)
- No per-question rows in Supabase
- incident_summary combines ALL user answers
- credibility_score generated once and stored permanently
"""

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime
import json
import uuid
import base64
import os

from app.db.local_db import LocalAsyncSession
from app.models.local_models import LocalSession, LocalConversation, LocalStateTracking, LocalEvidence, LocalSenderType
from app.models.beacon import Beacon
from app.schemas.report import MessageResponse
from app.services.llm_agent import LLMAgent
from app.models.report import SenderType
from uuid import UUID as UUIDType


class ReportEngine:
    """
    Backend Observer Pattern with Two-Tier Database.
    
    LOCAL SQLite stores:
    - Active chat sessions
    - Conversation messages
    - State tracking
    - Temporary evidence
    
    SUPABASE beacon table stores:
    - One row per case (INSERT once)
    - reported_at, case_id, incident_summary
    - credibility_score, score_explanation
    - evidence_files (Base64 encoded)
    """
    
    @staticmethod
    async def process_message(
        report_id: str,
        user_message: str,
        supabase_session: AsyncSession,
        background_tasks: "BackgroundTasks" = None
    ) -> MessageResponse:
        """
        Process a user message:
        1. Store user message in LOCAL SQLite
        2. Build conversation history from LOCAL
        3. Forward to LLM (LLM leads)
        4. Store LLM response in LOCAL
        5. Handle completion - INSERT to beacon if final
        """
        import traceback
        
        try:
            async with LocalAsyncSession() as local_session:
                # 1. Store user message locally
                user_msg = LocalConversation(
                    session_id=report_id,
                    sender=LocalSenderType.USER,
                    content=user_message
                )
                local_session.add(user_msg)
                await local_session.flush()
                
                # 2. Build conversation history from local DB
                stmt = select(LocalConversation).where(
                    LocalConversation.session_id == report_id
                ).order_by(LocalConversation.created_at)
                result = await local_session.execute(stmt)
                history_objs = result.scalars().all()
                
                # Convert to LLM format
                conversation_history = []
                for msg in history_objs:
                    role = "user" if msg.sender == LocalSenderType.USER else "assistant"
                    conversation_history.append({
                        "role": role,
                        "content": msg.content
                    })
                
                # 3. Forward to LLM (LLM is sole conversational authority)
                llm_response, final_report = await LLMAgent.chat(conversation_history)
                
                # 4. Store LLM response locally
                sys_msg = LocalConversation(
                    session_id=report_id,
                    sender=LocalSenderType.SYSTEM,
                    content=llm_response
                )
                local_session.add(sys_msg)
                
                # 5. Handle completion
                next_step = "ACTIVE"
                case_id = None
                
                if final_report:
                    next_step = "SUBMITTED"
                    
                    # Generate Unique Case ID
                    max_attempts = 100
                    attempts = 0
                    while attempts < max_attempts:
                        candidate_id = LLMAgent.generate_case_id()
                        # Check directly in Supabase beacon table
                        check_stmt = select(Beacon).where(Beacon.case_id == candidate_id)
                        check_res = await supabase_session.execute(check_stmt)
                        if not check_res.scalar_one_or_none():
                            case_id = candidate_id
                            break
                        attempts += 1
                    
                    if not case_id:
                        print(f"[REPORT_ENGINE] ERROR: Could not generate unique case ID after {max_attempts} attempts")
                        case_id = LLMAgent.generate_case_id()  # Use anyway as fallback
                    
                    # Get first message timestamp for reported_at
                    first_msg_stmt = select(LocalConversation).where(
                        LocalConversation.session_id == report_id
                    ).order_by(LocalConversation.created_at).limit(1)
                    first_msg_res = await local_session.execute(first_msg_stmt)
                    first_msg = first_msg_res.scalar_one_or_none()
                    reported_at = first_msg.created_at if first_msg else datetime.utcnow()
                    
                    # Gather evidence files as Base64
                    evidence_files = await ReportEngine._gather_evidence_base64(report_id, local_session)
                    
                    # SINGLE INSERT to beacon table
                    beacon_row = Beacon(
                        reported_at=reported_at,
                        case_id=case_id,
                        evidence_files=evidence_files
                        # incident_summary and credibility_score set via UPDATE in background
                    )
                    supabase_session.add(beacon_row)
                    
                    # Mark local session as submitted
                    local_sess_stmt = select(LocalSession).where(LocalSession.id == report_id)
                    local_sess_res = await local_session.execute(local_sess_stmt)
                    local_sess = local_sess_res.scalar_one_or_none()
                    if local_sess:
                        local_sess.is_submitted = True
                        local_sess.is_active = False
                        local_sess.case_id = case_id
                    
                    # Update state tracking
                    state_stmt = select(LocalStateTracking).where(LocalStateTracking.session_id == report_id)
                    state_res = await local_session.execute(state_stmt)
                    state = state_res.scalar_one_or_none()
                    if state:
                        state.current_step = "SUBMITTED"
                    
                    await local_session.commit()
                    
                    # Trigger Background Scoring (updates beacon via UPDATE)
                    from app.services.scoring_service import ScoringService
                    if background_tasks:
                        background_tasks.add_task(
                            ScoringService.run_background_scoring, 
                            report_id,  # session_id for local data
                            case_id     # case_id for beacon update
                        )
                    else:
                        print("[REPORT_ENGINE] WARNING: BackgroundTasks not provided for scoring.")
                
                await local_session.commit()
                await supabase_session.commit()
                
                # Log successful storage for debugging
                if final_report and case_id:
                    print(f"[REPORT_ENGINE] Created beacon entry with case_id: {case_id}")
                
                return MessageResponse(
                    report_id=UUIDType(report_id),  # Convert string to UUID
                    sender=SenderType.SYSTEM,
                    content=llm_response,
                    timestamp=datetime.utcnow(),
                    next_step=next_step,
                    case_id=case_id  # Include case_id in response when submitted
                )
        
        except Exception as e:
            print(f"[REPORT_ENGINE] ❌ ERROR processing message for {report_id}: {type(e).__name__}: {e}")
            traceback.print_exc()
            await supabase_session.rollback()
            raise

    @staticmethod
    async def _gather_evidence_base64(session_id: str, local_session: AsyncSession) -> list:
        """
        Gather all evidence files for a session and encode as Base64.
        Returns list of dicts with file_name, mime_type, size_bytes, content_base64.
        """
        evidence_files = []
        
        stmt = select(LocalEvidence).where(LocalEvidence.session_id == session_id)
        result = await local_session.execute(stmt)
        evidence_objs = result.scalars().all()
        
        for ev in evidence_objs:
            try:
                with open(ev.file_path, "rb") as f:
                    file_bytes = f.read()
                
                content_base64 = base64.b64encode(file_bytes).decode('utf-8')
                
                evidence_files.append({
                    "file_name": ev.file_name,
                    "mime_type": ev.mime_type,
                    "size_bytes": ev.size_bytes,
                    "file_hash": ev.file_hash,
                    "content_base64": content_base64
                })
            except Exception as e:
                print(f"[REPORT_ENGINE] Error reading evidence file {ev.file_path}: {e}")
                # Still include metadata even if file read fails
                evidence_files.append({
                    "file_name": ev.file_name,
                    "mime_type": ev.mime_type,
                    "size_bytes": ev.size_bytes,
                    "file_hash": ev.file_hash,
                    "content_base64": None,
                    "error": str(e)
                })
        
        return evidence_files

    @staticmethod
    async def initialize_report(report_id: str):
        """
        Initialize a new report session in LOCAL SQLite.
        
        NO greeting is stored here. The LLM will greet naturally
        when it receives the first user message.
        """
        async with LocalAsyncSession() as local_session:
            # Check if session already exists
            stmt = select(LocalSession).where(LocalSession.id == report_id)
            result = await local_session.execute(stmt)
            existing = result.scalar_one_or_none()
            
            if existing:
                print(f"[REPORT_ENGINE] Session {report_id} already exists")
                return
            
            # Initialize state tracking locally
            state_tracking = LocalStateTracking(
                session_id=report_id,
                current_step="ACTIVE",
                context_data={
                    "initialized_at": datetime.utcnow().isoformat(),
                    "extracted": {}
                }
            )
            local_session.add(state_tracking)
            await local_session.commit()
            
            print(f"[REPORT_ENGINE] ✅ Initialized local session: {report_id}")

    @staticmethod
    async def get_session_status(session_id: str) -> dict:
        """
        Get session status from local database.
        """
        async with LocalAsyncSession() as local_session:
            stmt = select(LocalSession).where(LocalSession.id == session_id)
            result = await local_session.execute(stmt)
            session = result.scalar_one_or_none()
            
            if not session:
                return {"error": "Session not found"}
            
            return {
                "session_id": session.id,
                "is_active": session.is_active,
                "is_submitted": session.is_submitted,
                "case_id": session.case_id,
                "created_at": session.created_at.isoformat() if session.created_at else None
            }
