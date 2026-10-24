"""Deterministic parts of credibility scoring.

The LLM judges narrative / evidence / behaviour; everything that can be computed is computed here so the
model cannot produce an inconsistent result (a total that is not the sum of its parts, a "High" label on a
score of 20, evidence points for a report that has no evidence ...).
"""

from app.schemas.ai import EvidenceDigest, FinalScore, ScoringResult

NARRATIVE_MAX = 40
EVIDENCE_MAX = 40
BEHAVIOR_MAX = 20

LOW_MAX = 33  # 0-33 Low, 34-66 Medium, 67-100 High (documented in the README)
MEDIUM_MAX = 66

MAX_POINTS = 12  # rationale / limitation items kept
MAX_POINT_CHARS = 600


def confidence_band(score: int) -> str:
    if score <= LOW_MAX:
        return "Low"
    if score <= MEDIUM_MAX:
        return "Medium"
    return "High"


def priority_for(score: int | None) -> str:
    """Admin triage label. Uses the same bands as the confidence level so the two never disagree."""
    return "Pending" if score is None else confidence_band(score)


def _clamp(value: int, maximum: int) -> int:
    return max(0, min(maximum, int(value)))


def _tidy(items: list[str]) -> list[str]:
    cleaned = [" ".join(item.split())[:MAX_POINT_CHARS] for item in items if item and item.strip()]
    return cleaned[:MAX_POINTS]


def has_usable_evidence(digests: list[EvidenceDigest]) -> bool:
    return any(d.status == "valid" and d.analysis_available and (d.description or d.extracted_text or d.transcript) for d in digests)


def finalize_score(result: ScoringResult, digests: list[EvidenceDigest]) -> FinalScore:
    narrative = _clamp(result.narrative_credibility.score, NARRATIVE_MAX)
    evidence = _clamp(result.evidence_strength.score, EVIDENCE_MAX)
    behavioral = _clamp(result.behavioral_reliability.score, BEHAVIOR_MAX)
    limitations = _tidy(result.limitations)

    if evidence and not has_usable_evidence(digests):
        # Documented rule: no (usable) evidence -> evidence strength is exactly 0.
        evidence = 0
        limitations.append("No usable supporting evidence could be analysed, so evidence strength was set to 0.")

    total = max(1, min(100, narrative + evidence + behavioral))  # the database rejects a score of 0
    return FinalScore(
        total=total,
        narrative=narrative,
        evidence=evidence,
        behavioral=behavioral,
        confidence=confidence_band(total),  # type: ignore[arg-type]
        rationale=_tidy(result.rationale),
        limitations=_tidy(limitations),
    )
