"""
Report Engine - Backend Observer Pattern with Cloud-Only Database (Supabase).

Data Flow:
1. Chat sessions, history, and state stored in SUPABASE staging tables (Report, ReportConversation, ReportStateTracking)
2. Finalized case data stored in SUPABASE beacon table (permanent)

Key Rules:
- ONE row per case in beacon table (INSERT once, UPDATE after)
- reported_at, case_id, incident_summary stored permanently
- Evidence metadata synced from Evidence table to Beacon on finalization
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

from app.db.session import AsyncSessionLocal
from app.models.report import (
    Report,
    ReportConversation,
    SenderType,
    ReportStateTracking,
    Evidence
)
from app.models.beacon import Beacon
from app.schemas.report import MessageResponse
from app.services.llm_agent import LLMAgent
from app.services.case_service import CaseService
from app.services.storage_service import StorageService
from uuid import UUID as UUIDType
from passlib.context import CryptContext
import logging
from fastapi import BackgroundTasks

pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")
logger = logging.getLogger(__name__)


class ReportEngine:
    """
    Backend Observer Pattern with Two-Tier Database.
    
    SUPABASE staging tables store:
    - Active chat sessions (Report)
    - Conversation messages (ReportConversation)
    - State tracking (ReportStateTracking)
    - Evidence metadata (Evidence)
    
    SUPABASE beacon table stores:
    - One row per case (INSERT once)
    - reported_at, case_id, incident_summary
    - credibility_score, score_explanation
    - evidence_files (JSON metadata)
    """
    
    @classmethod
    async def process_message(
        cls,
        report_id: str,
        user_message: str,
        supabase_session: AsyncSession,
        background_tasks: "BackgroundTasks" = None
    ) -> MessageResponse:
        """
        Process a user message:
        1. Store user message in Supabase
        2. Build conversation history from Supabase
        3. Forward to LLM
        4. Store LLM response in Supabase
        5. Handle completion - INSERT to beacon if final
        """
        try:
            # Stage 1: Store user message in Supabase
            print(f"[REPORT_ENGINE] STAGE 1: Store user message: {report_id}", flush=True)
            user_msg = ReportConversation(
                report_id=UUIDType(report_id),
                sender=SenderType.USER,
                content_redacted=user_message
            )
            supabase_session.add(user_msg)
            await supabase_session.flush()
            
            # 1.5. CHECK FOR & PROCESS NEW EVIDENCE
            ev_stmt = select(Evidence).where(Evidence.report_id == UUIDType(report_id)).order_by(Evidence.uploaded_at)
            ev_result = await supabase_session.execute(ev_stmt)
            evidence_items = list(ev_result.scalars().all())

            # 2. Build conversation history from Supabase
            stmt = select(ReportConversation).where(
                ReportConversation.report_id == UUIDType(report_id)
            ).order_by(ReportConversation.created_at)
            result = await supabase_session.execute(stmt)
            history_objs = result.scalars().all()
            
            # Fetch persistent state context from Supabase
            state_stmt = select(ReportStateTracking).where(ReportStateTracking.report_id == UUIDType(report_id))
            state_res = await supabase_session.execute(state_stmt)
            state_tracking = state_res.scalar_one_or_none()
            
            if not state_tracking:
                # Auto-initialize if missing
                await ReportEngine.initialize_report(report_id, "tk_auto_gen")
                state_stmt = select(ReportStateTracking).where(ReportStateTracking.report_id == UUIDType(report_id))
                state_res = await supabase_session.execute(state_stmt)
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
                        return f"File: {ev.file_name}"

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
                await supabase_session.flush()

            # Convert to LLM format
            conversation_history = []
            for msg in history_objs:
                role = "user" if msg.sender == SenderType.USER else "assistant"
                
                conversation_history.append({
                    "role": role,
                    "content": msg.content_redacted
                })
            
            # ... (inject evidence context omitted for brevity, logic remains same)
            if evidence_context_str:
                conversation_history.append({
                        "role": "system",
                        "content": f"[NEW EVIDENCE UPLOADED]\nAnalysis of files just uploaded: {evidence_context_str}"
                })

            # ... (LLM call remains same)
            llm_response, new_extracted_data = await LLMAgent.chat(conversation_history, current_state)
            
            if new_extracted_data and state_tracking:
                updated_state = current_state.copy()
                for k, v in new_extracted_data.items():
                    if v and v != "...":
                        updated_state[k] = v
                
                new_context_data = dict(state_tracking.context_data)
                new_context_data["extracted"] = updated_state
                state_tracking.context_data = new_context_data
                await supabase_session.flush()

            # 4. Store LLM response in Supabase
            sys_msg = ReportConversation(
                report_id=UUIDType(report_id),
                sender=SenderType.SYSTEM,
                content_redacted=llm_response
            )
            supabase_session.add(sys_msg)
            
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
                
                # Phase 1: INTAKE (FAIL-SAFE with Retries for Race Conditions)
                max_retries = 3
                retry_count = 0
                while retry_count < max_retries:
                    try:
                        case_id = await CaseService.generate_next_case_id(supabase_session)
                        
                        # Generate Unique Secret Key
                        secret_key_display = await CaseService.generate_unique_secret_key(supabase_session)
                        secret_key_hash = pwd_context.hash(secret_key_display)
                        
                        # Replace placeholders (Extremely Case-insensitive & Robust)
                        # This handles CASE_ID_PLACEHOLDER, CASE_ID_1234, etc.
                        temp_llm_response = re.sub(r"CASE_ID_(PLACEHOLDER|\d+)", case_id, llm_response, flags=re.IGNORECASE)
                        temp_llm_response = re.sub(r"SECRET_KEY_(PLACEHOLDER|\d+)", secret_key_display, temp_llm_response, flags=re.IGNORECASE)
                        
                        # Fallback Replacement: If AI still used a weird format or hallucinated a generic pattern
                        temp_llm_response = re.sub(r"(Case ID is:?\s*)([A-Z0-9_-]+)", rf"\g<1>{case_id}", temp_llm_response, flags=re.I)
                        temp_llm_response = re.sub(r"(Secret Key is:?\s*)([A-Z0-9_-]+)", rf"\g<1>{secret_key_display}", temp_llm_response, flags=re.I)

                        # FINAL SAFETY NET: If Secret Key is NOT in the text AND placeholders were missed
                        if secret_key_display not in temp_llm_response:
                                temp_llm_response = temp_llm_response.rstrip()
                                if not temp_llm_response.endswith("."):
                                    temp_llm_response += "."
                                temp_llm_response += f"\n\nYour Secret Key is {secret_key_display}. Please save this."
                        
                        # Get reported_at timestamp
                        from app.core.time_utils import get_utc_now
                        reported_at_utc = get_utc_now()
                        
                        # Phase 1.5: Gather evidence files metadata from Supabase
                        evidence_files = await cls._get_evidence_metadata(report_id, supabase_session)
                        
                        # Ensure incident summary is a paragraph and free of placeholders
                        raw_summary = final_report.get("incident_summary") or final_report.get("what") or "In-progress report"
                        # Strip placeholders if they leaked into the summary
                        clean_summary = re.sub(r"(CASE_ID|SECRET_KEY)_PLACEHOLDER", "", raw_summary, flags=re.I).strip()
                        # Ensure it doesn't end with a colon or weird character
                        clean_summary = re.sub(r"[:\s]+$", ".", clean_summary)
                        if not clean_summary.endswith("."): clean_summary += "."

                        new_case = Beacon(
                            case_id=case_id,
                            reported_at=reported_at_utc,
                            secret_key=secret_key_display,
                            secret_key_hash=secret_key_hash,
                            status="Received",
                            incident_summary=clean_summary,
                            evidence_files=evidence_files,
                            credibility_score=None,
                            credibility_breakdown=None,
                            analysis_status="pending"
                        )
                        supabase_session.add(new_case)
                        
                        # Update Report record in Supabase
                        stmt_rep = select(Report).where(Report.id == UUIDType(report_id))
                        rep_res = await supabase_session.execute(stmt_rep)
                        report_rec = rep_res.scalar_one_or_none()
                        if report_rec:
                            report_rec.case_id = case_id
                            report_rec.status = "NEW"

                        print(f"[REPORT_ENGINE] STAGE 4: Finalizing to Supabase: {case_id}", flush=True)
                        await supabase_session.commit()
                        
                        llm_response = temp_llm_response # Finalize the response text
                        print(f"[REPORT_ENGINE] STAGE 5: Phase 1 Intake Complete: {case_id}", flush=True)
                        logger.info(f"phase1_intake_complete: {case_id}")
                        next_step = "COMPLETED"
                        break # Success!
                        
                    except Exception as e:
                        # Explicitly handle IntegrityError for duplicate case IDs
                        from sqlalchemy.exc import IntegrityError
                        if isinstance(e, IntegrityError) or "UniqueViolationError" in str(e):
                            print(f"[REPORT_ENGINE] Race condition detected for {case_id}. Retrying {retry_count+1}/{max_retries}...", flush=True)
                            await supabase_session.rollback()
                            retry_count += 1
                            if retry_count >= max_retries:
                                raise e # Give up after 3 tries
                            continue
                        else:
                            # Other errors should be handled by the outer try-block
                            raise e

                # ---------------------------------------------------------
                # PHASE 2: TRIGGER ASYNC ANALYSIS
                # ---------------------------------------------------------
                if background_tasks:
                    print(f"[REPORT_ENGINE] Triggering automated background scoring for: {case_id}", flush=True)
                    from app.services.scoring_service import ScoringService
                    background_tasks.add_task(ScoringService.run_background_scoring, report_id, case_id)
                else:
                    print(f"[REPORT_ENGINE] WARNING: No background_tasks object found. Automated analysis NOT triggered for: {case_id}", flush=True)

            # Always commit all turns
            await supabase_session.commit()
            
            return MessageResponse(
                report_id=UUIDType(report_id),
                sender=SenderType.SYSTEM,
                content=llm_response,
                timestamp=datetime.now(timezone.utc),
                next_step=next_step,
                case_id=case_id,
                secret_key=secret_key_display if case_id else None
            )
        
        except Exception as e:
            print(f"[REPORT_ENGINE] ERROR in process_message: {e}", flush=True)
            await supabase_session.rollback()
            raise

    @classmethod
    async def _get_evidence_metadata(cls, session_id: str, supabase_session: AsyncSession) -> list:
        """Fetch and format evidence metadata for the beacon record."""
        from sqlalchemy import select
        stmt = select(Evidence).where(Evidence.report_id == UUIDType(session_id))
        result = await supabase_session.execute(stmt)
        evidence_objs = result.scalars().all()
        
        results = []
        for ev in evidence_objs:
            results.append({
                "file_name": ev.file_name,
                "mime_type": ev.mime_type,
                "size_bytes": ev.size_bytes,
                "file_path": ev.file_path,
                "full_url": StorageService.get_public_url(ev.file_path)
            })
        return results

    @classmethod
    async def initialize_report(cls, report_id: str, access_token: str):
        """
        Initialize a new report session in SUPABASE.
        """
        import hashlib
        token_hash = hashlib.sha256(access_token.encode()).hexdigest()

        async with AsyncSessionLocal() as supabase_session:
            # Check if session already exists
            stmt = select(Report).where(Report.id == UUIDType(report_id))
            result = await supabase_session.execute(stmt)
            existing = result.scalar_one_or_none()
            
            if existing:
                print(f"[REPORT_ENGINE] Session {report_id} already exists in Supabase", flush=True)
                return
            
            # Create Report (Supabase)
            new_report = Report(
                id=UUIDType(report_id),
                access_token_hash=token_hash,
                status="NEW"
            )
            supabase_session.add(new_report)

            # Initialize state tracking in Supabase
            state_tracking = ReportStateTracking(
                report_id=UUIDType(report_id),
                current_step="ACTIVE",
                context_data={
                    "initialized_at": datetime.now(timezone.utc).isoformat(),
                    "extracted": {}
                }
            )
            supabase_session.add(state_tracking)
            await supabase_session.commit()
            
            print(f"[REPORT_ENGINE] Initialized Supabase session: {report_id}", flush=True)

    @classmethod
    async def get_session_status(cls, session_id: str) -> dict:
        """
        Get session status from Supabase.
        """
        async with AsyncSessionLocal() as supabase_session:
            stmt = select(Report).where(Report.id == UUIDType(session_id))
            result = await supabase_session.execute(stmt)
            report = result.scalar_one_or_none()
            
            if not report:
                return {"error": "Report session not found"}
            
            return {
                "session_id": str(report.id),
                "is_active": report.status != "CLOSED",
                "is_submitted": report.case_id is not None,
                "case_id": report.case_id,
                "created_at": report.created_at.isoformat() if report.created_at else None
            }
