import asyncio
import structlog
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from fastapi.concurrency import run_in_threadpool
from app.db.session import SessionLocal
from app.models.report import Report
from app.models.evidence import Evidence
from app.services.ai_service import GroqService
from app.services.storage_service import StorageService
from app.services.evidence_processor import EvidenceProcessor

logger = structlog.get_logger()

class ScoringService:
    @staticmethod
    async def run_background_scoring(session_id: str, case_id: str):
        """
        Asynchronous task to:
        1. Fetch chat history and evidence
        2. Process evidence (OCR/Labels)
        3. Generate AI Summary & Score with aggressive backoff/retry-after
        4. Update Database
        """
        logger.info("background_scoring_start", case_id=case_id)
        
        async with asyncio.Lock(): # Prevent concurrent runs for same case if possible (though enqueued once)
            db = SessionLocal()
            try:
                # 1. DATA COLLECTION
                report = db.query(Report).filter(Report.case_id == case_id).first()
                if not report:
                    logger.error("report_not_found", case_id=case_id)
                    return

                chat_history = report.conversation_logs if report.conversation_logs else []
                evidence_objs = db.query(Evidence).filter(Evidence.case_id == case_id).all()

                # 2. LAYER 1: DETERMINISTIC PROCESSING
                evidence_metadata = await run_in_threadpool(EvidenceProcessor.process_evidence, evidence_objs)

                # 3. LAYER 2: AI REASONING (WITH PERSISTENT RETRY)
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
                    report.analysis_status = "failed"
                    report.analysis_error = "Summary generation failed (Rate Limited)"
                    db.commit()
                    return

                # --- FORENSIC ENRICHMENT ---
                # (OCR/Audio/Visual) - Using simple retries or skip on failure
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
                    result, retry_hint = await GroqService.calculate_credibility_score(chat_history, evidence_metadata, metadata_context, timeout=45.0)
                    if result:
                        score_result = result
                        break
                        
                    wait_time = retry_hint if retry_hint else backoff_times[attempt]
                    logger.info("bg_score_retry", case_id=case_id, attempt=attempt+1, wait=wait_time)
                    await asyncio.sleep(wait_time)

                if not score_result:
                    report.analysis_status = "failed"
                    report.analysis_error = "Credibility scoring failed (Rate Limited)"
                    db.commit()
                    return

                # 4. DATABASE UPDATE
                report.credibility_score = max(1, min(100, score_result.credibility_score))
                report.ai_summary = summary
                report.analysis_status = "completed"
                report.ai_explanation = {
                    "rationale": score_result.rationale,
                    "confidence": score_result.confidence_level,
                    "limitations": score_result.limitations,
                    "safety": score_result.final_safety_statement,
                    "narrative_score": score_result.narrative_credibility.score if score_result.narrative_credibility else 0,
                    "evidence_score": score_result.evidence_strength.score if score_result.evidence_strength else 0
                }
                
                # Sync results back to evidence objects if needed
                for ev_obj, ev_meta in zip(evidence_objs, evidence_metadata):
                    ev_obj.forensic_analysis = ev_meta.forensic_analysis
                    ev_obj.forensic_audio_analysis = ev_meta.forensic_audio_analysis
                    ev_obj.object_labels = ev_meta.object_labels

                db.commit()
                logger.info("background_scoring_success", case_id=case_id, score=report.credibility_score)

            except Exception as e:
                logger.error("background_scoring_failed", case_id=case_id, error=str(e))
                if db:
                    report = db.query(Report).filter(Report.case_id == case_id).first()
                    if report:
                        report.analysis_status = "failed"
                        report.analysis_error = str(e)
                        db.commit()
            finally:
                db.close()
