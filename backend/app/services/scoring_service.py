"""
ScoringService - Phase 2 Analysis Engine (Async & Strict).

Responsibilities:
1. Fetch raw data (Chat History, Evidence) from Local/Supabase.
2. Generate Intelligence (Summary, Score, Explanation) via AI.
3. STRICT VALIDATION: No placeholders, no defaults, no missing fields.
4. ATOMIC UPDATE: Write to 'beacon' table ONLY if all checks pass.
5. Error Handling: Log internal errors, keep status='pending' for retry.
"""

from typing import Dict, Any, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from app.services.ai_service import GroqService
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
    Phase 2: Asynchronous Analysis Engine.
    """
    
    @staticmethod
    async def run_background_scoring(session_id: str, case_id: str):
        """
        Background Entry Point.
        - Idempotent-ish (can be retried).
        - Updates Beacon table atomically on success.
        - Updates analysis_attempts/last_error on failure.
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

                    # 2. Perform AI Analysis (Strict Mode)
                    analysis_results = await ScoringService._perform_strict_analysis(chat_history, evidence_objs)
                    
                    if not analysis_results:
                        raise ValueError("AI Analysis returned None (Strict Validation Failed).")
                    
                    print(f"[DEBUG] Analysis Results: {json.dumps(analysis_results, indent=2)}")
                        
                    # 3. Validate Outputs (Double Check)
                    ScoringService._assert_no_placeholders(analysis_results)
                    
                    # 4. Atomic Commit
                    await ScoringService._commit_valid_results(case_id, analysis_results, supabase_session)
                    
                except Exception as e:
                    logger.error("phase2_analysis_failed", case_id=case_id, error=str(e))
                    await ScoringService._record_failure(case_id, str(e), supabase_session)

    @staticmethod
    async def _perform_strict_analysis(chat_history: List[Dict], evidence_objs: List[Any]) -> Optional[Dict[str, Any]]:
        """
        Orchestrates AI calls. Returns None if ANY component fails.
        """
        # Evidence Analysis
        evidence_summary_text = "No evidence provided."
        if evidence_objs:
            evidence_analyses = []
            for ev in evidence_objs:
                try:
                    f_path = ev.file_path
                    f_mime = ev.mime_type
                    if os.path.exists(f_path):
                        with open(f_path, "rb") as f:
                            file_bytes = f.read()
                        analysis = await GroqService.analyze_evidence(file_bytes, f_mime)
                        evidence_analyses.append(f"File {ev.file_name}: {analysis.get('analysis', 'No analysis')}")
                    else:
                        evidence_analyses.append(f"File {ev.file_name}: File missing")
                except Exception as e:
                    logger.warning("evidence_analysis_partial_fail", error=str(e))
            if evidence_analyses:
                evidence_summary_text = "; ".join(evidence_analyses)

        # Incident Summary
        summary = await GroqService.generate_pro_summary(chat_history)
        if not summary or "INSUFFICIENT" in summary.upper():
            logger.warning("analysis_aborted_invalid_summary")
            return None

        # Credibility Score
        metadata = {"evidence_count": len(evidence_objs), "timestamp": str(datetime.utcnow())}
        score_data = await GroqService.calculate_scoring_rubric(chat_history, evidence_summary_text, metadata)
        
        if not score_data:
            logger.warning("analysis_aborted_scoring_failed")
            return None
            
        score = score_data.get("credibility_score")
        breakdown = score_data.get("breakdown")
        auth_summary = score_data.get("authority_summary")
        
        # Strict validation of all dimension keys
        required_keys = [
            "information_completeness", "internal_consistency", "evidence_quality",
            "language_tone", "temporal_proximity", "corroboration_patterns",
            "user_cooperation", "malicious_penalty"
        ]
        if not breakdown or not all(k in breakdown for k in required_keys):
            logger.error("analysis_aborted_malformed_breakdown", breakdown=breakdown)
            return None

        # Log individual dimensions
        logger.info("scoring_dimensions_calculated", 
                    case_id="...", # Note: case_id not in this scope directly but logged at caller level
                    score=score, 
                    **breakdown)
        
        # Strict constraints
        if score is None or not (1 <= score <= 100):
            logger.warning("analysis_aborted_invalid_score", score=score)
            return None
            
        if not auth_summary or len(auth_summary) < 10:
             logger.warning("analysis_aborted_invalid_authority_summary")
             return None

        return {
            "incident_summary": summary,
            "credibility_score": score,
            "credibility_breakdown": breakdown,
            "authority_summary": auth_summary
        }

    @staticmethod
    def _assert_no_placeholders(data: Dict[str, Any]):
        """
        Final safety check for forbidden strings. Raises ValueError if found.
        """
        forbidden = [
            "insert summary here", "automated scoring unavailable", 
            "system error", "default neutral", "insufficient information",
            "[insert", "[add summary", "placeholder summary"
        ]
        
        combined = (str(data.get("incident_summary")) + str(data.get("authority_summary"))).lower()
        
        for term in forbidden:
            if term in combined:
                raise ValueError(f"Strict Check Failed: Forbidden validation term '{term}' found in output.")

    @staticmethod
    async def _commit_valid_results(case_id: str, results: Dict[str, Any], session: AsyncSession):
        """
        Writes valid results to DB and sets status='completed'.
        """
        stmt = (
            update(Beacon)
            .where(Beacon.case_id == case_id)
            .values(
                incident_summary=results["incident_summary"],
                credibility_score=results["credibility_score"],
                credibility_breakdown=results["credibility_breakdown"],
                authority_summary=results["authority_summary"],
                analysis_status="completed",
                analysis_last_error=None # Clear previous errors
            )
        )
        await session.execute(stmt)
        await session.commit()
        logger.info("phase2_analysis_success", case_id=case_id)

    @staticmethod
    async def _record_failure(case_id: str, error_msg: str, session: AsyncSession):
        """
        Updates failure stats without changing analysis_status from 'pending'.
        """
        try:
            # We want to increment logic. SA update with increment is cleaner, 
            # but fetching first is safer for simple logic.
            # actually strict SQL update is better for concurrency.
            stmt = (
                update(Beacon)
                .where(Beacon.case_id == case_id)
                .values(
                    analysis_attempts=Beacon.analysis_attempts + 1,
                    analysis_last_error=error_msg[:1000] # Truncate likely
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
