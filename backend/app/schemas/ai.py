from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from enum import Enum

# --- Forensic OCR Analysis Schema ---

class KeyElementsResults(BaseModel):
    dates: List[str] = Field(default_factory=list)
    amounts: List[str] = Field(default_factory=list)
    names: List[str] = Field(default_factory=list)
    locations: List[str] = Field(default_factory=list)
    official_markers: List[str] = Field(default_factory=list)

class ForensicOCRAnalysis(BaseModel):
    ocr_available: bool
    ocr_text_quality: str = Field(..., description="high | medium | low")
    key_elements_detected: KeyElementsResults
    narrative_alignment: str = Field(..., description="none | partial | strong")
    objective_notes: List[str]
    limitations: List[str]

# --- Forensic Audio/Video Analysis Schema ---

class AudioKeyElements(BaseModel):
    dates: List[str] = Field(default_factory=list)
    amounts: List[str] = Field(default_factory=list)
    names: List[str] = Field(default_factory=list)
    locations: List[str] = Field(default_factory=list)
    references: List[str] = Field(default_factory=list, description="References to documents, payments, official actions")

class ForensicAudioAnalysis(BaseModel):
    transcription_available: bool
    audio_clarity: str = Field(..., description="high | medium | low")
    key_elements_detected: AudioKeyElements
    narrative_alignment: str = Field(..., description="none | partial | strong")
    objective_notes: List[str]
    limitations: List[str]

# --- Layer 1: Deterministic Evidence Flags ---

class EvidenceType(str, Enum):
    IMAGE = "image"
    AUDIO = "audio"
    VIDEO = "video"
    DOCUMENT = "document"
    UNKNOWN = "unknown"

class EvidenceMetadata(BaseModel):
    file_name: str
    file_path: str
    file_type: EvidenceType
    
    # Deterministic Flags
    is_empty_or_corrupt: bool = False
    is_duplicate: bool = False
    file_hash: Optional[str] = None
    file_size: Optional[int] = None
    
    # Extraction Results
    ocr_text_snippet: Optional[str] = Field(None, description="First 500 chars of extracted text (if any)")
    object_labels: List[str] = Field(default_factory=list, description="Detected objects (e.g. ['invoice', 'cash'])")
    audio_transcript_snippet: Optional[str] = Field(None, description="First 500 chars of transcript")
    
    # Forensic Analysis (Layer 2)
    forensic_analysis: Optional[ForensicOCRAnalysis] = None
    forensic_audio_analysis: Optional[ForensicAudioAnalysis] = None
    
    # Relevance Signal (Still deterministic-ish heuristic, or simple keyword match)
    has_relevant_keywords: bool = False

# --- Layer 2: LLM Reasoning Output ---

class NarrativeCredibilityScore(BaseModel):
    score: int = Field(..., ge=0, le=40, description="0-40 score for consistency and details")
    # No strict Enums for reasons, just strings
    reasoning: List[str]

class EvidenceStrengthScore(BaseModel):
    score: int = Field(..., ge=0, le=40, description="0-40 score for evidence alignment")
    reasoning: List[str]

class BehavioralReliabilityScore(BaseModel):
    score: int = Field(..., ge=0, le=20, description="0-20 score for interaction quality")
    reasoning: List[str]

class ScoringResult(BaseModel):
    credibility_score: int = Field(..., ge=0, le=100)
    
    # Subscores
    narrative_credibility: NarrativeCredibilityScore
    evidence_strength: EvidenceStrengthScore
    behavioral_reliability: BehavioralReliabilityScore
    
    rationale: List[str] = Field(..., description="Objective, bullet-point explanation")
    confidence_level: str = Field(..., description="Low / Medium / High")
    
    limitations: str = Field(..., description="What could not be verified")
    final_safety_statement: str = Field(..., description="Mandatory disclaimer")

class AIAnalysisResult(BaseModel):
    summary: str
    entities: List[str]
    detected_language: str
    corruption_type_confidence: str
