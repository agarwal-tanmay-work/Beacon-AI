from typing import Dict, Any, Tuple
from app.services.ai_service import GeminiService
from app.schemas.ai import AICredibilityScore
import structlog

logger = structlog.get_logger()

class ScoringService:
    """
    Calculates a credibility score (0-100) for a report.
    Hybrid approach: Deterministic Base + AI Assessment.
    """

    @staticmethod
    async def calculate_score(context: Dict[str, Any], report_text_full: str) -> Tuple[int, str]:
        """
        Returns (score, explanation)
        """
        score = 0
        reasons = []

        # 1. Deterministic Factors (Base Score: 60%)
        # Completeness
        if context.get('location'):
            score += 10
            reasons.append("Location provided")
        if context.get('date'):
            score += 10
            reasons.append("Date provided")
        if context.get('roles'):
            score += 10
            reasons.append("Roles/Actors identified")
        
        # Specificity (Length of description)
        desc_len = len(context.get('description', ''))
        if desc_len > 50:
            score += 10
        if desc_len > 150:
            score += 10
            reasons.append("Detailed description")
            
        # Evidence (We assume 'evidence_uploaded' boolean or check context)
        # For now, we rely on 'evidence_desc' presence if no file
        if context.get('evidence_desc') and len(context.get('evidence_desc', '')) > 5:
             score += 10
             reasons.append("Evidence described/present")

        # Cap Deterministic Score at 60
        score = min(score, 60)
        
        # 2. AI Factors (Bonus Score: 40%)
        # Only if we have a decent base
        if score >= 20: 
            try:
                ai_result = await GeminiService.calculate_credibility(report_text_full, context)
                score += int(ai_result.score * 0.4) # Map 100 AI score to 40 points
                reasons.append(f"AI Assessment: {ai_result.reasoning}")
            except Exception as e:
                logger.error("scoring_ai_failed", error=str(e))
                reasons.append("AI verification unavailable")
        else:
            reasons.append("Insufficient data for AI verification")

        final_score = min(max(score, 0), 100)
        explanation = "; ".join(reasons)
        
        return final_score, explanation
