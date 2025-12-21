from pydantic import BaseModel, Field
from typing import List, Optional

class AIAnalysisResult(BaseModel):
    summary: str = Field(..., description="Concise summary of the report")
    entities: List[str] = Field(default_factory=list, description="Extracted relevant entities (people, places, orgs)")
    detected_language: str = Field(..., description="ISO language code detected")
    corruption_type_confidence: str = Field(..., description="Likely corruption type (e.g. Bribery)")

from enum import Enum

class ClarityLevel(str, Enum):
    EXTREMELY_VAGUE = "EXTREMELY_VAGUE"
    SOME_DETAILS_MAJOR_GAPS = "SOME_DETAILS_MAJOR_GAPS"
    MOST_DETAILS_MINOR_GAPS = "MOST_DETAILS_MINOR_GAPS"
    CLEAR_SPECIFIC = "CLEAR_SPECIFIC"

class ConsistencyLevel(str, Enum):
    CONTRADICTORY = "CONTRADICTORY"
    INCOHERENT = "INCOHERENT"
    MOSTLY_CONSISTENT = "MOSTLY_CONSISTENT"
    FULLY_COHERENT = "FULLY_COHERENT"

class EvidenceRelevance(str, Enum):
    NONE = "NONE"
    WEAK_UNCLEAR = "WEAK_UNCLEAR"
    RELEVANT_PARTIAL = "RELEVANT_PARTIAL"
    STRONG_DIRECT = "STRONG_DIRECT"

class ToneLabel(str, Enum):
    AGGRESSIVE_SENSATIONAL = "AGGRESSIVE_SENSATIONAL"
    EMOTIONAL_CHARGED = "EMOTIONAL_CHARGED"
    CALM_FACTUAL = "CALM_FACTUAL"

class MaliciousFlag(str, Enum):
    PERSONAL_VENDETTA = "PERSONAL_VENDETTA"
    UNSUPPORTED_ACCUSATIONS = "UNSUPPORTED_ACCUSATIONS"
    COPY_PASTE_CONTENT = "COPY_PASTE_CONTENT"
    FAKE_EVIDENCE = "FAKE_EVIDENCE"
    BOT_BEHAVIOR = "BOT_BEHAVIOR"
    NONE = "NONE"

class CredibilityFeatures(BaseModel):
    # 1. Information Completeness
    has_what: bool
    has_where: bool
    has_when: bool
    has_how: bool
    has_who: bool
    completeness_level: ClarityLevel

    # 2. Consistency
    consistency_level: ConsistencyLevel
    consistency_justification: str

    # 3. Evidence (AI Assessment of description/content)
    # Note: Quantity is calculated in code, but AI assesses quality of what fits
    evidence_quality_tier: EvidenceRelevance 
    evidence_tampering_suspected: bool

    # 4. Tone
    tone_label: ToneLabel
    
    # 5. Temporal (AI Extracts date)
    incident_date_extracted: Optional[str] = Field(None, description="ISO Date string YYYY-MM-DD if found")

    # 6. Malicious Check
    malicious_indicators: List[MaliciousFlag]
    
    # 7. Cooperation (AI assesses from chat history)
    user_responsiveness: str = Field(..., description="Assessment of user cooperation: 'EVASIVE', 'ADEQUATE', 'COOPERATIVE'")

    summary_narrative: str
