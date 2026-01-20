import asyncio
import structlog
from datetime import datetime, timezone
from sqlalchemy import select
from sqlalchemy.orm import Session
from fastapi.concurrency import run_in_threadpool

from app.db.session import AsyncSessionLocal

from app.models.beacon import Beacon
from app.models.report import ReportConversation, Evidence, SenderType
from app.services.ai_service import GroqService
from app.services.storage_service import StorageService
from app.services.evidence_processor import EvidenceProcessor

logger = structlog.get_logger()

class ScoringService:
    @staticmethod
    async def run_background_scoring(session_id: str, case_id: str):
        """
        Asynchronous task to:
        1. Fetch chat history from SQLite (LocalConversation)
        2. Fetch case from Supabase (Beacon)
        3. Fetch evidence from SQLite (LocalEvidence)
        4. Process evidence
        5. Generate AI Summary & Score
        6. Update Beacon in Supabase
        """
        logger.info("background_scoring_start", case_id=case_id)
        
        async with asyncio.Lock():
            # Open Supabase session
            async with AsyncSessionLocal() as remote_db:
                try:
                    # 1. Fetch case from Supabase
                    stmt = select(Beacon).where(Beacon.case_id == case_id)
                    result = await remote_db.execute(stmt)
                    beacon = result.scalar_one_or_none()
                    
                    if not beacon:
                        logger.error("beacon_not_found", case_id=case_id)
                        return

                    # 2. Fetch Chat History from Supabase (instead of local)
                    # We need the report_id (which is session_id in current context)
                    from uuid import UUID
                    history_stmt = select(ReportConversation).where(
                        ReportConversation.report_id == UUID(session_id)
                    ).order_by(ReportConversation.created_at.asc())
                    hist_res = await remote_db.execute(history_stmt)
                    history_objs = hist_res.scalars().all()
                    
                    chat_history = []
                    for msg in history_objs:
                        role = "user" if msg.sender == SenderType.USER else "assistant"
                        chat_history.append({"role": role, "content": msg.content_redacted})

                    # 3. Fetch Evidence from Supabase
                    ev_stmt = select(Evidence).where(Evidence.report_id == UUID(session_id))
                    ev_res = await remote_db.execute(ev_stmt)
                    evidence_objs = ev_res.scalars().all()

                    # 4. Process Evidence (OCR/Labels)
                    # We pass the Evidence model objects to the processor
                    evidence_metadata = await run_in_threadpool(EvidenceProcessor.process_evidence, list(evidence_objs))

                    # 5. AI Reasoning
                    summary = None
                    backoff_times = [10, 30, 60, 120]
                    
                    # --- SUMMARY GENERATION ---
                    for attempt in range(len(backoff_times)):
                        result, retry_hint = await GroqService.generate_pro_summary(chat_history, timeout=30.0)
                        if result:
                            summary = result
                            break
                        
                        wait_time = retry_hint if retry_hint else backoff_times[attempt]
                        logger.info("bg_summary_retry", case_id=case_id, attempt=attempt+1, wait=wait_time)
                        await asyncio.sleep(wait_time)

                    if not summary:
                        beacon.analysis_status = "failed"
                        beacon.analysis_last_error = "Summary generation failed (Rate Limited)"
                        await remote_db.commit()
                        return

                    # --- FORENSIC ENRICHMENT ---
                    for ev in evidence_metadata:
                        if ev.file_type == "image" and ev.ocr_text_snippet and len(ev.ocr_text_snippet) > 10:
                            analysis, _ = await GroqService.perform_forensic_ocr_analysis(ev.ocr_text_snippet, summary, timeout=20.0)
                            if analysis: ev.forensic_analysis = analysis

                        if ev.file_type == "audio" and ev.audio_transcript_snippet and len(ev.audio_transcript_snippet) > 10:
                            audio_analysis, _ = await GroqService.perform_forensic_audio_analysis(ev.audio_transcript_snippet, summary, timeout=20.0)
                            if audio_analysis: ev.forensic_audio_analysis = audio_analysis

                        if ev.file_type == "image":
                            try:
                                img_content = None
                                if ev.file_path.startswith("supastorage://"):
                                    parts = ev.file_path.replace("supastorage://", "").split("/", 1)
                                    img_content = await run_in_threadpool(StorageService.download_file, parts[0], parts[1])
                                else:
                                    img_content = await run_in_threadpool(lambda: open(ev.file_path, "rb").read())

                                visual_desc, _ = await GroqService.perform_forensic_visual_analysis(img_content, "image/jpeg", timeout=25.0)
                                if visual_desc: ev.object_labels.append(f"context: {visual_desc}")
                            except Exception: pass

                    # --- CREDIBILITY SCORING ---
                    metadata_context = {
                        "evidence_count": len(evidence_objs),
                        "timestamp": str(datetime.now(timezone.utc)),
                        "layer1_flags": [m.model_dump() for m in evidence_metadata]
                    }
                    
                    score_result = None
                    for attempt in range(len(backoff_times)):
                        scoring_res, retry_hint = await GroqService.calculate_credibility_score(chat_history, evidence_metadata, metadata_context, timeout=45.0)
                        if scoring_res:
                            score_result = scoring_res
                            break
                            
                        wait_time = retry_hint if retry_hint else backoff_times[attempt]
                        logger.info("bg_score_retry", case_id=case_id, attempt=attempt+1, wait=wait_time)
                        await asyncio.sleep(wait_time)

                    if not score_result:
                        beacon.analysis_status = "failed"
                        beacon.analysis_last_error = "Credibility scoring failed (Rate Limited)"
                        await remote_db.commit()
                        return

                    # 6. DATABASE UPDATE (Supabase)
                    beacon.credibility_score = max(1, min(100, score_result.credibility_score))
                    beacon.ai_summary = summary
                    beacon.ai_explanation = {
                        "rationale": score_result.rationale,
                        "confidence": score_result.confidence_level,
                        "limitations": score_result.limitations,
                        "safety": score_result.final_safety_statement,
                        "narrative_score": score_result.narrative_credibility.score if score_result.narrative_credibility else 0,
                        "evidence_score": score_result.evidence_strength.score if score_result.evidence_strength else 0
                    }
                    beacon.analysis_status = "completed"
                    
                    # Update score_explanation (Text) for compatibility with existing dashboard
                    beacon.score_explanation = f"Rationale: {', '.join(score_result.rationale or [])}\n\nConfidence: {score_result.confidence_level}\n\nLimitations: {', '.join(score_result.limitations or [])}"

                    # Sync forensic metadata back to the evidence_files JSON list in Beacon
                    if beacon.evidence_files:
                        updated_evidence_files = []
                        # We hope order matches between evidence_objs and beacon.evidence_files
                        # But it's safer to match by filename
                        for remote_ev in beacon.evidence_files:
                            match = next((m for m in evidence_metadata if m.file_name == remote_ev.get("file_name")), None)
                            if match:
                                remote_ev["forensic_analysis"] = match.forensic_analysis.model_dump() if hasattr(match.forensic_analysis, "model_dump") else match.forensic_analysis
                                remote_ev["forensic_audio_analysis"] = match.forensic_audio_analysis.model_dump() if hasattr(match.forensic_audio_analysis, "model_dump") else match.forensic_audio_analysis
                                remote_ev["object_labels"] = match.object_labels
                            updated_evidence_files.append(remote_ev)
                        beacon.evidence_files = updated_evidence_files

                    await remote_db.commit()
                    logger.info("background_scoring_success", case_id=case_id, score=beacon.credibility_score)

                except Exception as e:
                    logger.error("background_scoring_failed", case_id=case_id, error=str(e))
                    import traceback
                    traceback.print_exc()
                    try:
                        beacon.analysis_status = "failed"
                        beacon.analysis_last_error = str(e)
                        await remote_db.commit()
                    except: pass
