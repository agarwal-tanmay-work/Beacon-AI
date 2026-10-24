"""Request / response shapes of the public and admin APIs."""

from datetime import UTC, datetime
from typing import Annotated, Any, Literal
from uuid import UUID

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, PlainSerializer, field_validator

from app.core.config import settings
from app.models.report import SenderType

CaseStatus = Literal["Pending", "Ongoing", "Completed"]


def _as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def _iso_z(value: datetime) -> str:
    return _as_utc(value).strftime("%Y-%m-%dT%H:%M:%SZ")


# Always serialised as "2026-01-01T12:00:00Z" (SQLite hands back naive datetimes; they are UTC).
UTCDateTime = Annotated[datetime, AfterValidator(_as_utc), PlainSerializer(_iso_z, return_type=str)]


def _clean_text(value: str | None) -> str | None:
    if value is None:
        return None
    # Drop NUL / control characters (except newline and tab) that break storage and rendering.
    return "".join(ch for ch in value if ch in "\n\t" or ord(ch) >= 32).strip()


# ======================================================================================
# Reporting session (anonymous reporter <-> AI)
# ======================================================================================
class CreateReportRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")
    client_seed: str | None = Field(default=None, max_length=200)  # legacy field, ignored


class ReportResponse(BaseModel):
    report_id: UUID
    access_token: str
    message: str


class MessageRequest(BaseModel):
    report_id: UUID
    access_token: str = Field(min_length=8, max_length=300)
    content: str = Field(min_length=1, max_length=settings.MAX_MESSAGE_CHARS)

    @field_validator("content")
    @classmethod
    def _non_blank(cls, value: str) -> str:
        cleaned = _clean_text(value) or ""
        if not cleaned:
            raise ValueError("message must not be empty")
        return cleaned


class MessageResponse(BaseModel):
    report_id: UUID
    sender: SenderType
    content: str
    timestamp: UTCDateTime
    next_step: Literal["ACTIVE", "COMPLETED"] = "ACTIVE"
    case_id: str | None = None  # present when the report was just submitted
    secret_key: str | None = None  # present ONLY in the submission response (and until acknowledged)
    mode: Literal["ai", "basic"] = "ai"  # "basic" = the AI assistant was unavailable, standard questions were used
    notice: str | None = None


class SessionAuthRequest(BaseModel):
    report_id: UUID
    access_token: str = Field(min_length=8, max_length=300)


class CredentialsResponse(BaseModel):
    case_id: str
    secret_key: str


class EvidenceUploadResponse(BaseModel):
    status: Literal["success"] = "success"
    evidence_id: UUID
    file_name: str
    mime_type: str
    size_bytes: int
    hash: str


# ======================================================================================
# Case tracking (reporter, with Case ID + Secret Key)
# ======================================================================================
class MessageAttachment(BaseModel):
    file_name: str = Field(max_length=255)
    file_path: str = Field(max_length=600)  # storage reference when sent by a client; signed relative URL when returned
    mime_type: str = Field(max_length=100)


class TrackStatusRequest(BaseModel):
    case_id: str = Field(min_length=1, max_length=40)
    secret_key: str = Field(min_length=1, max_length=64)


class PublicUpdate(BaseModel):
    message: str
    timestamp: UTCDateTime


class TrackMessage(BaseModel):
    id: str
    sender_role: Literal["user", "admin"]
    content: str | None = None
    attachments: list[MessageAttachment] = Field(default_factory=list)
    timestamp: UTCDateTime


class TrackStatusResponse(BaseModel):
    status: str
    reported_at: UTCDateTime
    incident_summary: str | None = None
    last_updated: UTCDateTime
    updates: list[PublicUpdate] = Field(default_factory=list)
    messages: list[TrackMessage] = Field(default_factory=list)


class TrackMessageRequest(BaseModel):
    case_id: str = Field(min_length=1, max_length=40)
    secret_key: str = Field(min_length=1, max_length=64)
    content: str | None = Field(default=None, max_length=settings.MAX_MESSAGE_CHARS)
    attachments: list[MessageAttachment] = Field(default_factory=list, max_length=5)

    @field_validator("content")
    @classmethod
    def _clean(cls, value: str | None) -> str | None:
        return _clean_text(value) or None


class SecureUploadResponse(BaseModel):
    file_name: str
    file_path: str  # opaque storage reference: echo it back in ``attachments``
    mime_type: str
    size_bytes: int


# ======================================================================================
# Admin
# ======================================================================================
class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=1, max_length=500)


class AdminMessageRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")  # older admin builds also send case_id / secret_key placeholders
    content: str | None = Field(default=None, max_length=settings.MAX_MESSAGE_CHARS)
    attachments: list[MessageAttachment] = Field(default_factory=list, max_length=5)

    @field_validator("content")
    @classmethod
    def _clean(cls, value: str | None) -> str | None:
        return _clean_text(value) or None


class AdminUpdateRequest(BaseModel):
    raw_update: str = Field(min_length=1, max_length=settings.MAX_MESSAGE_CHARS)
    updated_by: str | None = Field(default="ADMIN", max_length=100)
    status: CaseStatus | None = None
    # Explicit opt-in to publish the text exactly as typed when the AI rewrite is unavailable.
    publish_raw: bool = False

    @field_validator("raw_update")
    @classmethod
    def _clean(cls, value: str) -> str:
        cleaned = _clean_text(value) or ""
        if not cleaned:
            raise ValueError("update must not be empty")
        return cleaned


class AdminUpdateResponse(BaseModel):
    status: str
    public_update: str
    timestamp: UTCDateTime
    rewritten: bool = True


class UpdateStatusRequest(BaseModel):
    status: CaseStatus


class CaseUpdateSchema(BaseModel):
    id: str
    public_update: str
    created_at: UTCDateTime
    updated_by: str


class AdminReportSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    case_id: str
    status: str
    priority: str
    credibility_score: int | None = None
    confidence: str | None = None
    created_at: UTCDateTime
    incident_summary: str | None = None
    ai_summary: str | None = None
    ai_explanation: dict[str, Any] | None = None
    analysis_status: str | None = "pending"
    app_score_explanation: str | None = None
    reporter_details: dict[str, Any] | None = None
    evidence_files: list[dict[str, Any]] = Field(default_factory=list)
    updates: list[CaseUpdateSchema] = Field(default_factory=list)
