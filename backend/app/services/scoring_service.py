
from typing import Dict, Any, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
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
from datetime import datetime

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

                    # 2. Layer 1: Deterministic Evidence Processing
                    evidence_metadata = EvidenceProcessor.process_evidence(evidence_objs)
                            
                    # 3. Layer 2: AI Reasoning
                    summary = await GroqService.generate_pro_summary(chat_history)
                    
                    # 3a. Forensic OCR Analysis (Enrichment)
                    # We iterate through processed evidence. If validation passed and we have OCR text, we analyze it.
                    for ev in evidence_metadata:
                        if ev.file_type == "image" and ev.ocr_text_snippet and len(ev.ocr_text_snippet) > 10:
                            # We limit to snippet to avoid huge context, or if we had full text stored, we'd use that.
                            # For now, using the snippet is consistent with the simple model.
                            # But ideally we want MORE than the snippet if available. 
                            # Since we don't store full text in metadata, we trust the snippet is representative or lengthy enough.
                            
                            logger.info("running_forensic_ocr", file=ev.file_name)
                            analysis = await GroqService.perform_forensic_ocr_analysis(
                                ocr_text=ev.ocr_text_snippet, # In real app, pass full text
                                narrative_summary=summary
                            )
                            if analysis:
                                ev.forensic_analysis = analysis
                    
                    # 3b. Forensic Audio Analysis (Enrichment)
                    for ev in evidence_metadata:
                        if ev.file_type == "audio" and ev.audio_transcript_snippet and len(ev.audio_transcript_snippet) > 10:
                            # Skip error messages
                            if ev.audio_transcript_snippet.startswith("["):
                                continue
                                
                            logger.info("running_forensic_audio", file=ev.file_name)
                            audio_analysis = await GroqService.perform_forensic_audio_analysis(
                                transcript_text=ev.audio_transcript_snippet,
                                narrative_summary=summary,
                                audio_metadata={"clarity": "medium"}  # Basic metadata
                            )
                            if audio_analysis:
                                ev.forensic_audio_analysis = audio_analysis
                    
                    # 3c. Forensic Visual Analysis (Enrichment)
                    for ev in evidence_metadata:
                        if ev.file_type == "image":
                            # We fetch the raw content for vision analysis
                            # Note: LocalEvidence stores the file_path
                            try:
                                with open(ev.file_path, "rb") as f:
                                    img_content = f.read()
                                
                                logger.info("running_forensic_visual", file=ev.file_name)
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
                        "timestamp": str(datetime.utcnow()),
                        "layer1_flags": [m.dict() for m in evidence_metadata] # Now includes forensic_analysis
                    }
                    
                    score_result = await GroqService.calculate_credibility_score(chat_history, evidence_metadata, metadata)
                    
                    if not score_result:
                         raise ValueError("AI Scoring returned None.")

                    # 4. Strict Validation
                    score = score_result.credibility_score
                    if not (0 <= score <= 100):
                         raise ValueError(f"Invalid Score: {score}")

                    # 5. Atomic Commit
                    # We map the new Pydantic models to JSON for storage
                    breakdown_json = {
                        "narrative": score_result.narrative_credibility.dict(),
                        "evidence": score_result.evidence_strength.dict(),
                        "behavioral": score_result.behavioral_reliability.dict(),
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
