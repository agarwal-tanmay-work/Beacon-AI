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
from datetime import datetime, timezone
import json
import uuid
import base64
import os
import asyncio
import re
import secrets

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
from app.services.case_service import CaseService
from app.models.report import SenderType
from uuid import UUID as UUIDType
from passlib.context import CryptContext
import secrets
import logging
from fastapi import BackgroundTasks

pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")
logger = logging.getLogger(__name__)


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
        try:
            async with LocalAsyncSession() as local_session:
                print(f"[REPORT_ENGINE] STAGE 1: Store user message: {report_id}", flush=True)
                user_msg = LocalConversation(
                    session_id=report_id,
                    sender=LocalSenderType.USER,
                    content=user_message
                )
                local_session.add(user_msg)
                await local_session.flush()
                
                # 1.5. CHECK FOR & PROCESS NEW EVIDENCE (FAST VISION MODE - Stage A)
                # Replaced heavy EvidenceProcessor with lightweight Grok Vision call
                from app.models.local_models import LocalEvidence
                
                # 1.5. CHECK FOR & PROCESS NEW EVIDENCE (FAST VISION/AUDIO MODE)
                # Replaced heavy EvidenceProcessor with lightweight Grok Vision call
                from app.models.local_models import LocalEvidence
                
                ev_stmt = select(LocalEvidence).where(LocalEvidence.session_id == report_id).order_by(LocalEvidence.uploaded_at)
                ev_result = await local_session.execute(ev_stmt)
                evidence_items = ev_result.scalars().all()
                evidence_items = list(evidence_items) # Ensure list

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
                
                if not state_tracking:
                    # Auto-initialize if missing (Safety Net)
                    await ReportEngine.initialize_report(report_id, "tk_auto_gen")
                    state_stmt = select(LocalStateTracking).where(LocalStateTracking.session_id == report_id)
                    state_res = await local_session.execute(state_stmt)
                    state_tracking = state_res.scalar_one_or_none()

                current_state = {}
                if state_tracking and state_tracking.context_data:
                    current_state = dict(state_tracking.context_data.get("extracted", {}))
                
                # --- NEW EVIDENCE LOGIC ---
                last_count = int(current_state.get("evidence_count", 0))
                current_count = len(evidence_items)
                
                evidence_context_str = ""
                
                if current_count > last_count:
                    new_items = evidence_items[last_count:]
                    
                    async def get_description(ev):
                        try:
                            mime = (ev.mime_type or "").lower()
                            if mime.startswith("image"):
                                desc = await LLMAgent.analyze_image_fast(ev.file_path)
                                return f"Image: {desc}"
                            elif mime.startswith("audio"):
                                desc = await LLMAgent.analyze_audio_fast(ev.file_path)
                                return f"Audio: {desc}"
                            else:
                                return f"File: {ev.file_name}"
                        except Exception:
                            return f"File: {ev.file_name} (Analysis failed)"

                    # Parallel Analysis
                    descriptions = await asyncio.gather(*(get_description(ev) for ev in new_items))
                    
                    evidence_context_str = "; ".join(descriptions)
                    
                    # Update State Immediately
                    current_state["evidence_count"] = current_count
                    current_state["evidence"] = "Uploaded" # Mark evidence as provided
                    
                    # Persist this specific state update immediately so we don't re-process if LLM crashes
                    new_context_data = dict(state_tracking.context_data or {})
                    new_context_data["extracted"] = current_state
                    state_tracking.context_data = new_context_data
                    await local_session.flush()

                # Convert to LLM format
                conversation_history = []
                for msg in history_objs:
                    sender_str = str(msg.sender).split('.')[-1] if '.' in str(msg.sender) else str(msg.sender)
                    role = "user" if sender_str == "USER" else "assistant"
                    
                    conversation_history.append({
                        "role": role,
                        "content": msg.content
                    })
                
                # INJECT EVIDENCE CONTEXT (System Injection)
                # ONLY inject if we just processed NEW evidence
                if evidence_context_str:
                    conversation_history.append({
                         "role": "system",
                         "content": f"[NEW EVIDENCE UPLOADED]\nAnalysis of files just uploaded: {evidence_context_str}"
                    })

                # 3. Forward to LLM (LLM is sole conversational authority)
                # Pass current_state to LLM so it knows what it ALREADY confirmed
                print(f"[REPORT_ENGINE] STAGE 2: LLM Request starting: {report_id}", flush=True)
                llm_response, new_extracted_data = await LLMAgent.chat(conversation_history, current_state)
                print(f"[REPORT_ENGINE] STAGE 3: LLM Response received: {len(llm_response or '')} chars", flush=True)
                
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
                    state_tracking.context_data = new_context_data  # CRITICAL: Assign back!
                    await local_session.flush()

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
                secret_key_display = None
                
                # Trigger submission based on PLACEHOLDERS (Case-insensitive check)
                # Also check for suspected hallucinated patterns if placeholder is missing but completion tone is detected
                completion_patterns = [
                    r"CASE_ID_PLACEHOLDER",
                    r"SECRET_KEY_PLACEHOLDER",
                    r"Your Case ID is:? [A-Z0-9_-]+", # Catch hallucinations like BCN-1234
                    r"Your Secret Key is:? [A-Z0-9_-]+"
                ]
                
                has_placeholder = any(re.search(p, llm_response, re.IGNORECASE) for p in completion_patterns)
                
                if has_placeholder:
                    # Force normalization of hallucinations to our standard placeholders for replacement
                    llm_response = re.sub(r"BCN-\d+", "CASE_ID_PLACEHOLDER", llm_response, flags=re.IGNORECASE)
                    
                    case_id = await CaseService.generate_next_case_id(supabase_session)
                    
                    # Generate Secret Key
                    raw_hex = secrets.token_hex(4).upper() 
                    secret_key_display = f"{raw_hex[:4]}-{raw_hex[4:]}"
                    secret_key_hash = pwd_context.hash(secret_key_display)
                    
                    # Replace placeholders (Extremely Case-insensitive & Robust)
                    llm_response = re.sub(r"CASE_ID_PLACEHOLDER", case_id, llm_response, flags=re.IGNORECASE)
                    llm_response = re.sub(r"SECRET_KEY_PLACEHOLDER", secret_key_display, llm_response, flags=re.IGNORECASE)
                    
                    # Fallback Replacement: If AI still used a weird format like "Case ID is BCN-123", overwrite it
                    llm_response = re.sub(r"(Case ID is\s+)([A-Z0-9-]+)", rf"\1{case_id}", llm_response, flags=re.I)
                    llm_response = re.sub(r"(Secret Key is\s+)([A-Z0-9-]+)", rf"\1{secret_key_display}", llm_response, flags=re.I)
                    
                    # Get reported_at timestamp
                    from app.core.time_utils import get_utc_now
                    reported_at_utc = get_utc_now()
                    
                    # Gather evidence files
                    evidence_files = await ReportEngine._upload_evidence_and_get_metadata(report_id, local_session)
                    
                    # ---------------------------------------------------------
                    # PHASE 1: INTAKE (FAIL-SAFE)
                    # ---------------------------------------------------------
                    # Create the actual Beacon record in Supabase
                    new_case = Beacon(
                        case_id=case_id,
                        reported_at=reported_at_utc,
                        secret_key=secret_key_display,
                        secret_key_hash=secret_key_hash,
                        status="Received",
                        incident_summary=final_report.get("incident_summary") or final_report.get("what") or "In-progress report",
                        evidence_files=evidence_files,
                        analysis_status="pending"
                    )
                    supabase_session.add(new_case)
                    
                    # Store case_id in local session too for tracking
                    from app.models.local_models import LocalSession
                    stmt_loc = select(LocalSession).where(LocalSession.id == report_id)
                    loc_res = await local_session.execute(stmt_loc)
                    loc_sess = loc_res.scalar_one_or_none()
                    if loc_sess:
                        loc_sess.case_id = case_id
                        loc_sess.is_submitted = True

                    print(f"[REPORT_ENGINE] STAGE 4: Finalizing to Supabase: {case_id}", flush=True)
                    # COMMIT PHASE 1 (RAW DATA)
                    await local_session.commit()
                    await supabase_session.commit()
                    
                    print(f"[REPORT_ENGINE] STAGE 5: Phase 1 Intake Complete: {case_id}", flush=True)
                    logger.info("phase1_intake_complete", case_id=case_id)

                    # ---------------------------------------------------------
                    # PHASE 2: TRIGGER ASYNC ANALYSIS
                    # ---------------------------------------------------------
                    if background_tasks:
                        from app.services.scoring_service import ScoringService
                        background_tasks.add_task(ScoringService.run_background_scoring, report_id, case_id)

                # Always commit local session (messages + state) for every turn
                await local_session.commit()
                
                return MessageResponse(
                    report_id=UUIDType(report_id),  # Convert string to UUID
                    sender=SenderType.SYSTEM,
                    content=llm_response,
                    timestamp=datetime.now(timezone.utc),
                    next_step=next_step,
                    case_id=case_id,  # Include case_id in response when submitted
                    secret_key=secret_key_display if case_id else None # Return ONLY ONCE
                )
        
        except Exception as e:
            print(f"[REPORT_ENGINE] ERROR in process_message: {e}", flush=True)
            try:
                await local_session.rollback()
            except: pass
            try:
                await supabase_session.rollback()
            except: pass
            raise

    @staticmethod
    async def _upload_evidence_and_get_metadata(session_id: str, local_session: AsyncSession) -> list:
        """
        Uploads evidence files to Supabase Storage in parallel and returns metadata list.
        """
        from app.services.storage_service import StorageService
        import asyncio
        
        stmt = select(LocalEvidence).where(LocalEvidence.session_id == session_id)
        result = await local_session.execute(stmt)
        evidence_objs = result.scalars().all()
        
        if not evidence_objs:
            return []

        async def upload_single(ev):
            try:
                with open(ev.file_path, "rb") as f:
                    file_bytes = f.read()
                return await StorageService.upload_file(file_bytes, ev.file_name, ev.mime_type)
            except Exception as e:
                print(f"[REPORT_ENGINE] Error uploading evidence file {ev.file_path}: {e}")
                return {"file_name": ev.file_name, "error": str(e)}

        # Run all uploads in parallel
        results = await asyncio.gather(*(upload_single(ev) for ev in evidence_objs))
        return list(results)

    @staticmethod
    async def initialize_report(report_id: str, access_token: str):
        """
        Initialize a new report session in LOCAL SQLite.
        """
        import hashlib
        token_hash = hashlib.sha256(access_token.encode()).hexdigest()

        async with LocalAsyncSession() as local_session:
            # Check if session already exists
            stmt = select(LocalSession).where(LocalSession.id == report_id)
            result = await local_session.execute(stmt)
            existing = result.scalar_one_or_none()
            
            if existing:
                print(f"[REPORT_ENGINE] Session {report_id} already exists", flush=True)
                return
            
            # Create LocalSession
            new_session = LocalSession(
                id=report_id,
                access_token_hash=token_hash,
                is_active=True,
                is_submitted=False
            )
            local_session.add(new_session)

            # Initialize state tracking locally
            state_tracking = LocalStateTracking(
                session_id=report_id,
                current_step="ACTIVE",
                context_data={
                    "initialized_at": datetime.now(timezone.utc).isoformat(),
                    "extracted": {}
                }
            )
            local_session.add(state_tracking)
            await local_session.commit()
            
            print(f"[REPORT_ENGINE] Initialized local session: {report_id}", flush=True)

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
