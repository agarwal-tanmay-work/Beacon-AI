"""
Scoring Service - Comprehensive Credibility Analysis.

Updates beacon table via UPDATE (never INSERT).
Generates:
- incident_summary: Combines ALL user answers
- credibility_score: Integer 1-100 (permanent)
- score_explanation: Detailed reasoning
"""

from typing import Dict, Any, List
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
import base64

logger = structlog.get_logger()


class ScoringService:
    """
    Orchestrates the Comprehensive Credibility Scoring Workflow.
    
    Key: Updates beacon table via UPDATE, never creates new rows.
    """
    
    @staticmethod
    async def run_background_scoring(session_id: str, case_id: str):
        """
        Background task to calculate scores and UPDATE beacon table.
        
        Args:
            session_id: Local session ID (for fetching conversation history)
            case_id: Beacon case_id (for updating beacon table)
        """
        logger.info("background_scoring_started", session_id=session_id, case_id=case_id)
        
        async with AsyncSessionLocal() as supabase_session:
            async with LocalAsyncSession() as local_session:
                try:
                    results = await ScoringService.calculate_comprehensive_score(
                        session_id, 
                        local_session
                    )
                    
                    if results:
                        # UPDATE beacon table (never INSERT)
                        stmt = (
                            update(Beacon)
                            .where(Beacon.case_id == case_id)
                            .values(
                                incident_summary=results.get("incident_summary"),
                                credibility_score=results.get("credibility_score"),
                                score_explanation=results.get("score_explanation")
                            )
                        )
                        await supabase_session.execute(stmt)
                        await supabase_session.commit()
                        
                        logger.info(
                            "background_scoring_completed", 
                            case_id=case_id, 
                            score=results.get("credibility_score")
                        )
                    else:
                        logger.warning("background_scoring_no_results", case_id=case_id)
                        
                except Exception as e:
                    logger.error("background_scoring_failed", case_id=case_id, error=str(e))
                    import traceback
                    traceback.print_exc()

    @staticmethod
    async def calculate_comprehensive_score(
        session_id: str, 
        local_session: AsyncSession
    ) -> Dict[str, Any]:
        """
        Full analysis pipeline:
        1. Fetch ALL conversation history from local DB
        2. Generate incident_summary combining ALL user answers
        3. Extract credibility features
        4. Calculate deterministic score
        5. Generate score_explanation
        
        Returns dict with incident_summary, credibility_score, score_explanation.
        """
        
        # 1. Fetch ALL conversation history from local DB
        conv_stmt = select(LocalConversation).where(
            LocalConversation.session_id == session_id
        ).order_by(LocalConversation.created_at)
        conv_res = await local_session.execute(conv_stmt)
        history_objs = conv_res.scalars().all()
        
        if not history_objs:
            logger.error("no_conversation_history", session_id=session_id)
            return {}
        
        chat_history = []
        for msg in history_objs:
            role = "user" if msg.sender == LocalSenderType.USER else "assistant"
            chat_history.append({"role": role, "content": msg.content})
        
        # 2. Fetch evidence info
        ev_stmt = select(LocalEvidence).where(LocalEvidence.session_id == session_id)
        ev_res = await local_session.execute(ev_stmt)
        evidence_objs = ev_res.scalars().all()
        
        evidence_count = len(evidence_objs)
        evidence_summary_text = "No evidence provided."
        evidence_analysis_results = []
        
        if evidence_objs:
            evidence_analyses = []
            for ev in evidence_objs:
                try:
                    with open(ev.file_path, "rb") as f:
                        file_bytes = f.read()
                    
                    analysis = await GroqService.analyze_evidence(file_bytes, ev.mime_type)
                    evidence_analyses.append(f"File {ev.file_name}: {analysis.get('analysis', 'No analysis')}")
                    evidence_analysis_results.append({
                        "file_name": ev.file_name,
                        "analysis": analysis
                    })
                except Exception as e:
                    logger.error("evidence_read_failed", file_path=ev.file_path, error=str(e))
                    evidence_analyses.append(f"File {ev.file_name}: Analysis failed")
            
            evidence_summary_text = "; ".join(evidence_analyses)
        
        # 3. Generate Professional Summary (combines ALL user answers)
        # This is critical: include EVERYTHING user provided, exclude nothing
        summary_text = await GroqService.generate_pro_summary(chat_history)
        
        if not summary_text or summary_text == "None":
            summary_text = "Insufficient information provided by the reporter."
        
        # 4. Extract Credibility Features
        metadata = {
            "created_at": history_objs[0].created_at if history_objs else None,
            "evidence_count": evidence_count
        }
        
        features = await GroqService.extract_credibility_features(
            chat_history, 
            evidence_summary_text, 
            metadata
        )
        
        if not features:
            logger.error("scoring_failed_no_features", session_id=session_id)
            # Fallback to basic scoring
            return {
                "incident_summary": summary_text,
                "credibility_score": 50,  # Default middle score
                "score_explanation": "Unable to perform full credibility analysis. Default score assigned."
            }
        
        # 5. Deterministic Scoring
        from app.core.scoring_logic import calculate_deterministically
        
        score_result = calculate_deterministically(features, metadata)
        
        final_score = max(1, min(score_result["final_score"], 100))
        justification = score_result["justification"]
        
        return {
            "incident_summary": summary_text,
            "credibility_score": final_score,
            "score_explanation": justification
        }
