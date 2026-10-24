"""Shapes exchanged with the LLM.

These models double as (a) the JSON Schema sent to Gemini and (b) the lenient validators for what
comes back. Anything the server can compute itself (totals, confidence band, disclaimers) is NOT part of
the LLM output, so the model cannot get it wrong.
"""

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

FACT_FIELDS = ("what", "where", "when", "who", "evidence", "contact_info", "other_details")
BASIC_FIELDS = ("what", "where", "when", "who")
SKIPPED = "SKIPPED"  # the reporter chose not to / could not answer
ASKED_ABOUT_VALUES = [*FACT_FIELDS, "none"]


def _as_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, list | tuple):
        return "; ".join(_as_text(v) for v in value if _as_text(v))
    return str(value).strip()


# ======================================================================================
# Conversational intake
# ======================================================================================
class ExtractedFacts(BaseModel):
    what: str = ""
    where: str = ""
    when: str = ""
    who: str = ""
    evidence: str = ""
    contact_info: str = ""
    other_details: str = ""

    @field_validator(*FACT_FIELDS, mode="before")
    @classmethod
    def _coerce(cls, value: Any) -> str:
        return _as_text(value)


class ChatTurn(BaseModel):
    """One assistant turn: what to say, what was learned, what was asked, and whether to submit."""

    reply: str
    extracted: ExtractedFacts = Field(default_factory=ExtractedFacts)
    asked_about: str = Field(default="none", json_schema_extra={"enum": ASKED_ABOUT_VALUES})
    ready_to_submit: bool = False

    @field_validator("reply", mode="before")
    @classmethod
    def _reply_text(cls, value: Any) -> str:
        text = _as_text(value)
        if not text:
            raise ValueError("reply must not be empty")
        return text

    @field_validator("asked_about", mode="before")
    @classmethod
    def _known_field(cls, value: Any) -> str:
        text = _as_text(value).lower()
        return text if text in ASKED_ABOUT_VALUES else "none"


# ======================================================================================
# Evidence
# ======================================================================================
class EvidenceKind:
    IMAGE = "image"
    AUDIO = "audio"
    DOCUMENT = "document"
    UNKNOWN = "unknown"


class ImageAnalysis(BaseModel):
    """Single vision call per image: what it shows and any text in it (replaces separate OCR + scene calls)."""

    description: str = Field(description="One or two neutral sentences: people/roles, setting, key objects (cash, documents, badges).")
    visible_text: str = Field(description="All legible text, verbatim, in reading order. Empty string if there is none.")
    legible: bool = Field(description="False if the image is too blurry, dark or small to be useful as evidence.")

    @field_validator("description", "visible_text", mode="before")
    @classmethod
    def _text(cls, value: Any) -> str:
        return _as_text(value)


class EvidenceDigest(BaseModel):
    """What the credibility scorer is told about one uploaded file."""

    file_name: str
    kind: str = EvidenceKind.UNKNOWN
    status: Literal["valid", "duplicate", "corrupt"] = "valid"
    description: str = ""
    extracted_text: str = ""
    transcript: str = ""
    quality_notes: list[str] = Field(default_factory=list)
    analysis_available: bool = True


# ======================================================================================
# Credibility scoring
# ======================================================================================
class SubScore(BaseModel):
    score: int = Field(ge=0, le=100, description="Points awarded within this dimension's maximum.")
    reasoning: list[str] = Field(default_factory=list)

    @field_validator("reasoning", mode="before")
    @classmethod
    def _list(cls, value: Any) -> list[str]:
        if isinstance(value, str):
            return [value] if value.strip() else []
        return [str(v) for v in value or []]


class ScoringResult(BaseModel):
    narrative_credibility: SubScore = Field(description="0-40")
    evidence_strength: SubScore = Field(description="0-40")
    behavioral_reliability: SubScore = Field(description="0-20")
    rationale: list[str] = Field(description="Objective plain-language explanation points.")
    limitations: list[str] = Field(description="What could not be verified.")

    @field_validator("rationale", "limitations", mode="before")
    @classmethod
    def _list(cls, value: Any) -> list[str]:
        if isinstance(value, str):
            return [value] if value.strip() else []
        return [str(v) for v in value or []]


class FinalScore(BaseModel):
    """ScoringResult after server-side validation: bounded sub-scores, recomputed total and band."""

    total: int
    narrative: int
    evidence: int
    behavioral: int
    confidence: Literal["Low", "Medium", "High"]
    rationale: list[str]
    limitations: list[str]
