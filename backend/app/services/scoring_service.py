from typing import Dict, Any, Tuple, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.services.ai_service import GroqService
from app.models.report import Report, Evidence
from app.db.session import AsyncSessionLocal
import structlog
import asyncio
import json

logger = structlog.get_logger()

class ScoringService:
    """
    Orchestrates the Comprehensive Credibility Scoring Workflow.
    Uses Groq API for multi-modal analysis.
    """
    
    @staticmethod
    async def run_background_scoring(report_id: str):
        """
        Wrapper for background execution. 
        Manages its own DB session to avoid detached session errors.
        """
        logger.info("background_scoring_started", report_id=report_id)
        async with AsyncSessionLocal() as session:
            try:
                results = await ScoringService.calculate_comprehensive_score(report_id, session)
                
                # Update Report with results
                if results:
                    stmt = select(Report).where(Report.id == report_id)
                    res = await session.execute(stmt)
                    report = res.scalar_one_or_none()
                    
                    if report:
                        report.incident_summary = results.get("incident_summary")
                        report.evidence_analysis = results.get("evidence_analysis")
                        report.tone_analysis = results.get("tone_analysis")
                        report.consistency_score = results.get("consistency_score")
                        report.fabrication_risk_score = results.get("fabrication_risk_score")
                        report.credibility_score = results.get("credibility_score")
                        report.score_explanation = results.get("score_explanation")
                        
                        await session.commit()
                        logger.info("background_scoring_completed", report_id=report_id, score=report.credibility_score)
                else:
                    logger.warning("background_scoring_no_results", report_id=report_id)
            except Exception as e:
                logger.error("background_scoring_failed", report_id=report_id, error=str(e))

    @staticmethod
    async def calculate_comprehensive_score(report_id: str, session: AsyncSession) -> Dict[str, Any]:
        """
        Runs the full analysis pipeline:
        1. Fetch all data (chat history, evidence).
        2. Run parallel AI tasks (Tone, Fabrication, Summary).
        3. Run Evidence Analysis (if images exist).
        4. Run Consistency Check (Summary vs Evidence).
        5. Compute Weighted Score.
        6. Generate Justification.
        
        Returns a dict of updates to apply to the Report model.
        """
        # 1. Fetch Data
        stmt = select(Report).where(Report.id == report_id)
        result = await session.execute(stmt)
        report = result.scalar_one_or_none()
        
        if not report:
            logger.error("report_not_found_for_scoring", report_id=report_id)
            return {}

        # Fetch conversation history from DB or report.conversations relation if lazy loaded
        # Ideally we fetch clean history. Let's assume we can get it via relation or query.
        # Check if loaded, if not, load.
        # For safety, let's query conversations explicitly to get order
        from app.models.report import ReportConversation, SenderType
        c_stmt = select(ReportConversation).where(ReportConversation.report_id == report_id).order_by(ReportConversation.created_at)
        c_res = await session.execute(c_stmt)
        history_objs = c_res.scalars().all()
        
        chat_history = []
        for msg in history_objs:
            role = "user" if msg.sender == SenderType.USER else "assistant"
            chat_history.append({"role": role, "content": msg.content_redacted})

        # Fetch Evidence
        e_stmt = select(Evidence).where(Evidence.report_id == report_id)
        e_res = await session.execute(e_stmt)
        evidence_objs = e_res.scalars().all()

        # 2. Parallel AI Tasks (Base Analysis)
        # We run these concurrently for speed
        
        # Task A: Generate Pro Summary
        t_summary = GroqService.generate_pro_summary(chat_history)
        
        # Task B: Analyze Tone
        t_tone = GroqService.analyze_tone(chat_history)
        
        # Task C: Detect Fabrication
        t_fabrication = GroqService.detect_fabrication(chat_history)
        
        # Execute Tasks A, B, C
        summary_text, tone_data, fab_data = await asyncio.gather(t_summary, t_tone, t_fabrication)
        
        # 3. Evidence Analysis
        evidence_analysis_results = []
        evidence_summary_text = "No evidence provided."
        
        if evidence_objs:
            evidence_analyses = []
            for ev in evidence_objs:
                # We need file bytes. 
                # In a real app, we'd read from storage service.
                # Here, we'll assume we can read from disk based on file_path if local, 
                # or skip if mapped to object store URL without download logic implemented here.
                # Implementation Assumption: Local uploads folder.
                try:
                    # simplistic read for MVP
                    with open(ev.file_path, "rb") as f:
                        file_bytes = f.read()
                    
                    # Analyze
                    analysis = await GroqService.analyze_evidence(file_bytes, ev.mime_type)
                    evidence_analyses.append(f"File {ev.file_name}: {analysis.get('analysis', 'No analysis')}")
                    evidence_analysis_results.append({
                        "file_name": ev.file_name,
                        "analysis": analysis
                    })
                except Exception as e:
                    logger.error("evidence_read_failed", file_path=ev.file_path, error=str(e))
                    evidence_analyses.append(f"File {ev.file_name}: Analysis failed (Read Error)")

            evidence_summary_text = "; ".join(evidence_analyses)
        
        # 4. Consistency Check (Needs Summary + Evidence Analysis)
        consistency_data = await GroqService.check_consistency(summary_text, evidence_summary_text)
        
        # 5. Compute Weighted Score
        # Formula:
        # Base: Consistency (40%) + Tone Logic (20%) + Detail Richness (Tone Spec) (20%)
        # Penalties: Fabrication High Risk (-50), Medium Risk (-20)
        # Bonus: Strong Corroborated Evidence (+20)
        
        # Parse inputs
        cons_score = consistency_data.get("score", 50)
        
        # Tone scores (heuristic mapping)
        logical_map = {"High": 100, "Medium": 70, "Low": 30}
        vagueness_map = {"High": 30, "Medium": 70, "Low": 100} # Low vagueness is good
        
        logic_score = logical_map.get(tone_data.get("logical_consistency", "Medium"), 50)
        detail_score = vagueness_map.get(tone_data.get("vagueness_level", "Medium"), 50)
        
        fab_risk_score = fab_data.get("risk_score", 0)
        
        # Weighted Calc
        raw_score = (cons_score * 0.45) + (logic_score * 0.25) + (detail_score * 0.30)
        
        # Penalties
        if fab_risk_score > 70:
            raw_score -= 50
        elif fab_risk_score > 40:
            raw_score -= 20
            
        final_score = int(min(max(raw_score, 1), 100))
        
        # 6. Generate Justification
        justification_lines = [
            f"**Final Credibility Score**: {final_score}/100",
            f"**Summary**: {summary_text}",
            "---",
            "**Analysis Breakdown**:",
            f"- **Consistency**: {cons_score}/100 ({consistency_data.get('match_status', 'N/A')}) - {consistency_data.get('reasoning', '')}",
            f"- **Logical Flow**: {tone_data.get('logical_consistency', 'N/A')}",
            f"- **Detail Level**: {tone_data.get('vagueness_level', 'N/A')}",
            f"- **Fabrication Risk**: {fab_risk_score}/100 ({fab_data.get('assessment', 'N/A')})",
            "---",
            "**Evidence Analysis**:",
            evidence_summary_text
        ]
        
        return {
            "incident_summary": summary_text,
            "evidence_analysis": evidence_analysis_results,
            "tone_analysis": tone_data,
            "consistency_score": cons_score,
            "fabrication_risk_score": fab_risk_score,
            "credibility_score": final_score,
            "score_explanation": "\n".join(justification_lines)
        }
