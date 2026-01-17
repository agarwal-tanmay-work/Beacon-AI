
from typing import Dict, Any, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from fastapi.concurrency import run_in_threadpool
from app.services.ai_service import GroqService
from app.services.evidence_processor import EvidenceProcessor
from app.models.beacon import Beacon
from app.db.session import AsyncSessionLocal
from app.db.local_db import LocalAsyncSession
from app.models.local_models import LocalConversation, LocalEvidence, LocalSenderType
import structlog
import asyncio
import json
import os
from datetime import datetime, timezone

logger = structlog.get_logger()

class ScoringService:
    """
    Phase 2: Asynchronous Analysis Engine (Two-Layer Architecture).
    """
    
    @staticmethod
    async def run_background_scoring(session_id: str, case_id: str):
        """
        Background Entry Point.
        """
        logger.info("phase2_analysis_started", session_id=session_id, case_id=case_id)
        
        async with AsyncSessionLocal() as supabase_session:
            async with LocalAsyncSession() as local_session:
                try:
                    # 1. Fetch Raw Data
                    chat_history = await ScoringService._fetch_chat_history(session_id, local_session)
                    evidence_objs = await ScoringService._fetch_evidence(session_id, local_session)
                    
                    if not chat_history:
                        raise ValueError("No chat history found for analysis.")

                    # 1.5 Ensure evidence is local for processing (Download if needed)
                    import tempfile
                    from app.services.storage_service import StorageService
                    
                    for ev in evidence_objs:
                        if ev.file_path.startswith("supastorage://"):
                            try:
                                # Handle Local Fallback
                                if "local_fallback" in ev.file_path:
                                    # Logic: The content should have been saved in the metadata if we used fallback
                                    # However, LocalEvidence object might NOT have it populated by default unless we specifically query for it
                                    # OR we stored it in 'context_data' or similar?
                                    # Wait, in report_engine we saved it to `record.evidence_data` (metadata).
                                    # LocalEvidence in `local_models.py` usually mirrors this.
                                    # Let's hope `ev` has access to the full metadata. 
                                    # If `ev` is a LocalEvidence instance, does it have the base64 content?
                                    # If NOT, we must fetch the `LocalSession` again and look at `evidence_data`.
                                    
                                    # EFFICIENT FIX:
                                    logger.info("using_local_fallback_evidence", file=ev.file_name)
                                    stmt_meta = select(LocalConversation).where(LocalConversation.session_id == session_id).limit(1)
                                    # Actually we need LocalSession object
                                    # `LocalEvidence` is linked to `LocalSession`? 
                                    # Let's just query the LocalSession table directly using session_id (which is report_id)
                                    from app.models.local_models import LocalSession
                                    stmt_ls = select(LocalSession).where(LocalSession.id == session_id)
                                    res_ls = await local_session.execute(stmt_ls)
                                    ls_rec = res_ls.scalar_one_or_none()
                                    
                                    file_bytes = None
                                    if ls_rec and ls_rec.evidence_data:
                                        for item in ls_rec.evidence_data:
                                            # Match by name
                                            if item.get("name") == ev.file_name:
                                                 if "content_b64" in item:
                                                     import base64
                                                     file_bytes = base64.b64decode(item["content_b64"])
                                                 break
                                    
                                    if not file_bytes:
                                        logger.warning("local_fallback_content_missing", file=ev.file_name)
                                        continue
                                        
                                else:
                                    # Standard Supabase Download
                                    # Format: supastorage://bucket/path/to/file
                                    parts = ev.file_path.replace("supastorage://", "").split("/", 1)
                                    if len(parts) == 2:
                                        bucket_name, remote_path = parts
                                        file_bytes = await run_in_threadpool(StorageService.download_file, bucket_name, remote_path)
                                    else:
                                        continue

                                # Save to temp file (Common for both paths)
                                if file_bytes:
                                    suffix = os.path.splitext(ev.file_name)[1]
                                    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
                                        tmp.write(file_bytes)
                                        ev.file_path = tmp.name # Update in-memory path for processor
                                        logger.info("evidence_ready_for_analysis", case_id=case_id, temp_path=ev.file_path)

                            except Exception as dl_err:
                                logger.error("evidence_download_failed", file=ev.file_name, error=str(dl_err))

                    # 2. Layer 1: Deterministic Evidence Processing (Run in threadpool as it's synchronous)
                    evidence_metadata = await run_in_threadpool(EvidenceProcessor.process_evidence, evidence_objs)
                            
                    # 3. Layer 2: AI Reasoning (with simple background retry for 429s)
                    summary = None
                    for attempt in range(2):
                        summary = await GroqService.generate_pro_summary(chat_history)
                        if summary: break
                        if attempt == 0: 
                            logger.info("background_scoring_retry_429", case_id=case_id)
                            await asyncio.sleep(5) # Small wait since it's background
                    
                    if not summary:
                         raise ValueError("AI Scoring summary generation failed (Rate Limited).")
 
                    # 3a. Forensic OCR Analysis (Enrichment)
                    # We iterate through processed evidence. If validation passed and we have OCR text, we analyze it.
                    for ev in evidence_metadata:
                        if ev.file_type == "image" and ev.ocr_text_snippet and len(ev.ocr_text_snippet) > 10:
                            logger.info("running_forensic_ocr", file=ev.file_name)
                            analysis = await GroqService.perform_forensic_ocr_analysis(
                                ocr_text=ev.ocr_text_snippet,
                                narrative_summary=summary
                            )
                            if analysis:
                                ev.forensic_analysis = analysis
                    
                    # 3b. Forensic Audio Analysis (Enrichment)
                    for ev in evidence_metadata:
                        if ev.file_type == "audio" and ev.audio_transcript_snippet and len(ev.audio_transcript_snippet) > 10:
                            if ev.audio_transcript_snippet.startswith("["):
                                continue
                                
                            logger.info("running_forensic_audio", file=ev.file_name)
                            audio_analysis = await GroqService.perform_forensic_audio_analysis(
                                transcript_text=ev.audio_transcript_snippet,
                                narrative_summary=summary,
                                audio_metadata={"clarity": "medium"}
                            )
                            if audio_analysis:
                                ev.forensic_audio_analysis = audio_analysis
                    
                    # 3c. Forensic Visual Analysis (Enrichment)
                    for ev in evidence_metadata:
                        if ev.file_type == "image":
                            try:
                                logger.info("running_forensic_visual", file=ev.file_name)
                                
                                img_content = None
                                if ev.file_path.startswith("supastorage://"):
                                    from app.services.storage_service import StorageService
                                    bucket_path = ev.file_path.replace("supastorage://evidence/", "")
                                    img_content = await run_in_threadpool(StorageService.download_file, "evidence", bucket_path)
                                else:
                                    img_content = await run_in_threadpool(lambda: open(ev.file_path, "rb").read())

                                visual_desc = await GroqService.perform_forensic_visual_analysis(
                                    image_bytes=img_content,
                                    mime_type="image/png" if ev.file_name.lower().endswith(".png") else "image/jpeg"
                                )
                                if visual_desc:
                                    ev.object_labels.append(f"context: {visual_desc}")
                            except Exception as e:
                                logger.warning("visual_forensic_failed", error=str(e))

                    metadata = {
                        "evidence_count": len(evidence_objs),
                        "timestamp": str(datetime.now(timezone.utc)),
                        "layer1_flags": [m.model_dump() for m in evidence_metadata]
                    }
                    
                    score_result = None
                    for attempt in range(2):
                        score_result = await GroqService.calculate_credibility_score(chat_history, evidence_metadata, metadata)
                        if score_result: break
                        if attempt == 0: await asyncio.sleep(5)

                    if not score_result:
                         raise ValueError("AI Scoring returned None (Rate Limited).")

                    # 4. Strict Validation
                    score = max(1, min(100, score_result.credibility_score))
                    if not (1 <= score <= 100):
                         raise ValueError(f"Invalid Score: {score}")

                    # 5. Atomic Commit
                    # We map the new Pydantic models to JSON for storage
                    breakdown_json = {
                        "narrative": score_result.narrative_credibility.model_dump(),
                        "evidence": score_result.evidence_strength.model_dump(),
                        "behavioral": score_result.behavioral_reliability.model_dump(),
                        "rationale": score_result.rationale,
                        "confidence": score_result.confidence_level,
                        "limitations": score_result.limitations,
                        "safety_statement": score_result.final_safety_statement
                    }
                    
                    stmt = (
                        update(Beacon)
                        .where(Beacon.case_id == case_id)
                        .values(
                            incident_summary=summary,
                            credibility_score=score,
                            credibility_breakdown=breakdown_json,
                            score_explanation="\n".join(score_result.rationale), # Legacy field fallback
                            authority_summary=f"Confidence: {score_result.confidence_level}. {score_result.final_safety_statement}",
                            analysis_status="completed",
                            analysis_last_error=None
                        )
                    )
                    await supabase_session.execute(stmt)
                    await supabase_session.commit()
                    
                    logger.info("phase2_analysis_success", case_id=case_id, score=score)
                    
                except Exception as e:
                    logger.error("phase2_analysis_failed", case_id=case_id, error=str(e))
                    await ScoringService._record_failure(case_id, str(e), supabase_session)

    @staticmethod
    async def _record_failure(case_id: str, error_msg: str, session: AsyncSession):
        try:
            stmt = (
                update(Beacon)
                .where(Beacon.case_id == case_id)
                .values(
                    analysis_attempts=Beacon.analysis_attempts + 1,
                    analysis_last_error=error_msg[:1000]
                )
            )
            await session.execute(stmt)
            await session.commit()
        except Exception as e:
            logger.error("failure_recording_failed", error=str(e))

    @staticmethod
    async def _fetch_chat_history(session_id: str, local_session: AsyncSession) -> List[Dict]:
        stmt = select(LocalConversation).where(
            LocalConversation.session_id == session_id
        ).order_by(LocalConversation.created_at)
        result = await local_session.execute(stmt)
        objs = result.scalars().all()
        return [{"role": "user" if m.sender == LocalSenderType.USER else "assistant", "content": m.content} for m in objs]

    @staticmethod
    async def _fetch_evidence(session_id: str, local_session: AsyncSession) -> List[LocalEvidence]:
        stmt = select(LocalEvidence).where(LocalEvidence.session_id == session_id)
        result = await local_session.execute(stmt)
        return result.scalars().all()
