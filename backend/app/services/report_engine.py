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
from app.models.local_models import (
    LocalSession, 
    LocalConversation, 
    LocalSenderType,
    LocalStateTracking
)
from app.models.local_models import LocalEvidence
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
            print(f"[REPORT_ENGINE] ===== Processing message for {report_id} =====")
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
                
                # Fetch persistent state context
                state_stmt = select(LocalStateTracking).where(LocalStateTracking.session_id == report_id)
                state_res = await local_session.execute(state_stmt)
                state_tracking = state_res.scalar_one_or_none()
                
                current_state = {}
                if state_tracking and state_tracking.context_data:
                    current_state = state_tracking.context_data.get("extracted", {})
                
                # Convert to LLM format
                conversation_history = []
                for msg in history_objs:
                    sender_str = str(msg.sender).split('.')[-1] if '.' in str(msg.sender) else str(msg.sender)
                    role = "user" if sender_str == "USER" else "assistant"
                    
                    conversation_history.append({
                        "role": role,
                        "content": msg.content
                    })
                
                # 3. Forward to LLM (LLM is sole conversational authority)
                # Pass current_state to LLM so it knows what it ALREADY confirmed
                llm_response, new_extracted_data = await LLMAgent.chat(conversation_history, current_state)
                print(f"[REPORT_ENGINE] LLM Response received: {len(llm_response)} chars, new_extracted={bool(new_extracted_data)}")
                
                # Update persistent state if new info discovered
                if new_extracted_data and state_tracking:
                    # Merge logic: New data overwrites/adds to old data
                    updated_state = current_state.copy()
                    for k, v in new_extracted_data.items():
                        if v and v != "...": # Only merge meaningful data
                            updated_state[k] = v
                    
                    # Store back to context_data
                    # Use a fresh dict to ensure SQLAlchemy detects change
                    new_context_data = dict(state_tracking.context_data)
                    new_context_data["extracted"] = updated_state
                    state_tracking.context_data = new_context_data
                    await local_session.flush()
                    print(f"[REPORT_ENGINE] Local state updated: {updated_state.keys()}")

                # 4. Store LLM response locally
                sys_msg = LocalConversation(
                    session_id=report_id,
                    sender=LocalSenderType.SYSTEM,
                    content=llm_response
                )
                local_session.add(sys_msg)
                
                # Use merged state for final report if submittted
                final_report = new_extracted_data if new_extracted_data else current_state

                
                # 5. Handle completion
                next_step = "ACTIVE"
                case_id = None
                
                # Trigger submission ONLY if placeholder is detected in text
                # This ensures the AI leads the conversation closure.
                if "CASE_ID_PLACEHOLDER" in llm_response:
                    next_step = "SUBMITTED"
                    
                    # Generate Incremental Case ID via CaseService
                    from app.services.case_service import CaseService
                    # We need a supabase session for reading existing max IDs
                    case_id = await CaseService.generate_next_case_id(supabase_session)
                    
                    # Replace placeholder in LLM response
                    llm_response = llm_response.replace("CASE_ID_PLACEHOLDER", case_id)
                    
                    # Get reported_at timestamp (IST via time_utils)
                    from app.core.time_utils import get_ist_now
                    reported_at_ist = get_ist_now()
                    
                    # Gather evidence files (Phase 1: Attempt upload, log partial failures, but do not block)
                    evidence_files = await ReportEngine._upload_evidence_and_get_metadata(report_id, local_session)
                    
                    # ---------------------------------------------------------
                    # PHASE 1: INTAKE (FAIL-SAFE)
                    # Store Raw Data Immediately. No AI / Scoring here.
                    # ---------------------------------------------------------
                    
                    beacon_row = Beacon(
                        reported_at=reported_at_ist,
                        case_id=case_id,
                        evidence_files=evidence_files,
                        created_at=reported_at_ist, 
                        updated_at=reported_at_ist,
                        # Phase 1 Fields
                        analysis_status="pending",
                        analysis_attempts=0,
                        # AI Fields - Explicitly NULL
                        incident_summary=None,
                        credibility_score=None
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
                    
                    # COMMIT INTELLIGENCE (RAW DATA)
                    await local_session.commit()
                    await supabase_session.commit()
                    
                    print(f"[REPORT_ENGINE] ✅ Phase 1 Complete. Report {case_id} stored safely.")

                    # ---------------------------------------------------------
                    # PHASE 2: TRIGGER ASYNC ANALYSIS
                    # ---------------------------------------------------------
                    if background_tasks:
                        from app.services.scoring_service import ScoringService
                        background_tasks.add_task(ScoringService.run_background_scoring, report_id, case_id)
                        print(f"[REPORT_ENGINE] 🚀 Phase 2 Triggered (Async Scoring) for {case_id}")
                    else:
                        print(f"[REPORT_ENGINE] ⚠️ No BackgroundTasks object! Phase 2 skipped (Manually trigger required).")

                # Always commit local session (messages + state) for every turn
                await local_session.commit()
                
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
    async def _upload_evidence_and_get_metadata(session_id: str, local_session: AsyncSession) -> list:
        """
        Uploads evidence files to Supabase Storage and returns metadata list.
        """
        from app.services.storage_service import StorageService
        
        evidence_files = []
        
        stmt = select(LocalEvidence).where(LocalEvidence.session_id == session_id)
        result = await local_session.execute(stmt)
        evidence_objs = result.scalars().all()
        
        for ev in evidence_objs:
            try:
                with open(ev.file_path, "rb") as f:
                    file_bytes = f.read()
                
                # Upload to Supabase
                upload_meta = await StorageService.upload_file(file_bytes, ev.file_name, ev.mime_type)
                evidence_files.append(upload_meta)
                
            except Exception as e:
                print(f"[REPORT_ENGINE] Error uploading evidence file {ev.file_path}: {e}")
                # Store error metadata
                evidence_files.append({
                    "file_name": ev.file_name,
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
