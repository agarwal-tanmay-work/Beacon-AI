from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from app.schemas.ai import CredibilityFeatures, ClarityLevel, ConsistencyLevel, EvidenceRelevance, ToneLabel, MaliciousFlag

def calculate_deterministically(features: CredibilityFeatures, metadata: Dict[str, Any]) -> Dict[str, Any]:
    """
    Calculates the final credibility score based on extracted features and strict scoring rules.
    """
    breakdown = {
        "completeness": 0,
        "consistency": 0,
        "evidence": 0,
        "tone": 0,
        "temporal": 0,
        "corroboration": 0,
        "cooperation": 0,
        "penalties": 0
    }
    
    # 1. Information Completeness (0-20)
    # Logic: Base score from Clarity Level + Bonus for W-questions
    clarity_base = {
        ClarityLevel.EXTREMELY_VAGUE: 3,
        ClarityLevel.SOME_DETAILS_MAJOR_GAPS: 8,
        ClarityLevel.MOST_DETAILS_MINOR_GAPS: 13,
        ClarityLevel.CLEAR_SPECIFIC: 16
    }
    comp_score = clarity_base.get(features.completeness_level, 5)
    
    # Bonus points for confirmed W-fields (max 4 bonus)
    w_count = sum([features.has_what, features.has_where, features.has_when, features.has_how, features.has_who])
    comp_score += min(w_count, 4)
    breakdown["completeness"] = min(comp_score, 20)

    # 2. Consistency (0-15)
    const_map = {
        ConsistencyLevel.CONTRADICTORY: 0,
        ConsistencyLevel.INCOHERENT: 3,
        ConsistencyLevel.MOSTLY_CONSISTENT: 10,
        ConsistencyLevel.FULLY_COHERENT: 15
    }
    breakdown["consistency"] = const_map.get(features.consistency_level, 8)

    # 3. Evidence Quality (0-25)
    # Logic: Quality Tier + Quantity Check? (Quantity is hard to judge from summary, relying on Tier)
    ev_map = {
        EvidenceRelevance.NONE: 0,
        EvidenceRelevance.WEAK_UNCLEAR: 5,
        EvidenceRelevance.RELEVANT_PARTIAL: 12,
        EvidenceRelevance.STRONG_DIRECT: 20 # Can go up to 25 with bonus for multiple files?
    }
    ev_score = ev_map.get(features.evidence_quality_tier, 0)
    
    # Bonus for clean metadata or multiple files? 
    # Let's add a small bonus if evidence exists and we have relevant metadata in the 'metadata' dict if passed.
    # For now, simplistic mapping.
    if features.evidence_quality_tier == EvidenceRelevance.STRONG_DIRECT and not features.evidence_tampering_suspected:
        ev_score += 5 # Push to 25 max
    
    if features.evidence_tampering_suspected:
        ev_score = 0 # Invalidate evidence score if tempered
        
    breakdown["evidence"] = min(ev_score, 25)

    # 4. Tone (0-10)
    tone_map = {
        ToneLabel.AGGRESSIVE_SENSATIONAL: 2,
        ToneLabel.EMOTIONAL_CHARGED: 6,
        ToneLabel.CALM_FACTUAL: 10
    }
    breakdown["tone"] = tone_map.get(features.tone_label, 5)

    # 5. Temporal Proximity (0-10)
    # Logic: Calculate delta(ReportDate - IncidentDate)
    temp_score = 5 # Default if no date
    if features.incident_date_extracted and metadata.get("created_at"):
        try:
            inc_date = datetime.fromisoformat(features.incident_date_extracted).date()
            rep_date = metadata["created_at"].date() if isinstance(metadata["created_at"], datetime) else datetime.utcnow().date()
            
            delta_days = (rep_date - inc_date).days
            
            if delta_days < 7: temp_score = 10
            elif delta_days < 30: temp_score = 8
            elif delta_days < 90: temp_score = 6
            elif delta_days < 365: temp_score = 4
            else: temp_score = 2
            
            if delta_days < 0: # Future date? Contradiction
                temp_score = 0
                breakdown["consistency"] -= 5 # Penalty for future date
                
        except Exception:
            pass # Keep default
            
    breakdown["temporal"] = max(0, min(temp_score, 10))

    # 6. Corroboration (0-10)
    # Placeholder: We check if metadata has 'pattern_match_score' injected by a separate service
    breakdown["corroboration"] = metadata.get("pattern_match_score", 0)

    # 7. User Cooperation (0-5)
    coop_map = {
        "EVASIVE": 0,
        "ADEQUATE": 3,
        "COOPERATIVE": 5
    }
    # Heuristic matching of the string
    resp = features.user_responsiveness.upper()
    if "COOPERATIVE" in resp: breakdown["cooperation"] = 5
    elif "ADEQUATE" in resp: breakdown["cooperation"] = 3
    elif "EVASIVE" in resp: breakdown["cooperation"] = 0
    else: breakdown["cooperation"] = 3 # Default
    
    # 8. Penalties (-15 to 0)
    penalty = 0
    if MaliciousFlag.PERSONAL_VENDETTA in features.malicious_indicators: penalty -= 5
    if MaliciousFlag.UNSUPPORTED_ACCUSATIONS in features.malicious_indicators: penalty -= 5
    if MaliciousFlag.FAKE_EVIDENCE in features.malicious_indicators: penalty -= 10
    if MaliciousFlag.BOT_BEHAVIOR in features.malicious_indicators: penalty -= 15
    if MaliciousFlag.COPY_PASTE_CONTENT in features.malicious_indicators: penalty -= 5
    
    breakdown["penalties"] = max(penalty, -15) # Cap penalty
    
    # Final Sum
    raw_total = sum(breakdown.values())
    final_score = int(max(1, min(raw_total, 100)))
    
    return {
        "final_score": final_score,
        "breakdown": breakdown,
        "justification": _generate_justification(final_score, features, breakdown)
    }

def _generate_justification(score: int, features: CredibilityFeatures, breakdown: Dict[str, int]) -> str:
    lines = [
        f"**Credibility Score**: {score}/100",
        f"**Assessment**: {features.summary_narrative}",
        "---",
        "**Scoring Logic**:",
        f"- Completeness ({breakdown['completeness']}/20): {features.completeness_level.value.replace('_', ' ').title()}",
        f"- Consistency ({breakdown['consistency']}/15): {features.consistency_level.value.replace('_', ' ').title()}",
        f"- Evidence ({breakdown['evidence']}/25): {features.evidence_quality_tier.value.replace('_', ' ').title()}",
        f"- Tone ({breakdown['tone']}/10): {features.tone_label.value.replace('_', ' ').title()}",
        f"- Temporal ({breakdown['temporal']}/10): Extracted Date: {features.incident_date_extracted or 'None'}",
        f"- Cooperation ({breakdown['cooperation']}/5): {features.user_responsiveness}",
        f"- Penalties ({breakdown['penalties']}): {', '.join([f.value for f in features.malicious_indicators if f != MaliciousFlag.NONE])}"
    ]
    return "\n".join(lines)
