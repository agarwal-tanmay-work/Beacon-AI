"""Chat-session ("staging") tables: one ``reports`` row per conversation, its messages, state and evidence.

When a conversation is submitted a permanent ``beacon`` row is created (see ``beacon.py``).

Columns marked *legacy* exist in already-deployed databases as NOT NULL without a server default, so
they must stay in the model (with a Python-side default) or INSERTs against those databases would fail.
"""

import enum
import uuid
from datetime import UTC, datetime

from sqlalchemy import JSON, Boolean, Column, DateTime, Enum, ForeignKey, Integer, String, Text, Uuid
from sqlalchemy.orm import relationship

from app.db.base import Base


def _now() -> datetime:
    return datetime.now(UTC)


class ReportStatus(str, enum.Enum):
    NEW = "NEW"
    ANALYZING = "ANALYZING"
    VERIFIED = "VERIFIED"
    IN_REVIEW = "IN_REVIEW"
    ESCALATED = "ESCALATED"
    CLOSED = "CLOSED"
    DISMISSED = "DISMISSED"


class ReportPriority(str, enum.Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class SenderType(str, enum.Enum):
    USER = "USER"
    AI = "AI"
    SYSTEM = "SYSTEM"  # assistant turns are stored as SYSTEM (kept for compatibility with existing rows)


class Report(Base):
    __tablename__ = "reports"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    case_id = Column(String(15), unique=True, nullable=True, index=True)  # set once the report is submitted
    access_token_hash = Column(String(255), unique=True, nullable=False, index=True)  # sha256 of the session token
    status = Column(Enum(ReportStatus), default=ReportStatus.NEW, nullable=False, index=True)
    priority = Column(Enum(ReportPriority), default=ReportPriority.LOW, nullable=False, index=True)  # legacy
    analysis_status = Column(String(20), default="pending", nullable=False)  # legacy (lives on `beacon` now)
    is_archived = Column(Boolean, default=False, nullable=False)  # legacy
    created_at = Column(DateTime(timezone=True), default=_now, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=_now, onupdate=_now, nullable=False)

    conversations = relationship("ReportConversation", back_populates="report", cascade="all, delete-orphan")
    state_tracking = relationship("ReportStateTracking", back_populates="report", uselist=False, cascade="all, delete-orphan")
    evidence = relationship("Evidence", back_populates="report", cascade="all, delete-orphan")


class ReportConversation(Base):
    __tablename__ = "report_conversations"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    report_id = Column(Uuid(as_uuid=True), ForeignKey("reports.id"), nullable=False, index=True)
    sender = Column(Enum(SenderType), nullable=False)
    content_redacted = Column(Text, nullable=False)  # name kept for compatibility; holds the message text
    intent_detected = Column(String(100), nullable=True)  # legacy, unused
    created_at = Column(DateTime(timezone=True), default=_now, nullable=False)

    report = relationship("Report", back_populates="conversations")


class ReportStateTracking(Base):
    """Per-conversation working state.

    ``context_data`` keys: ``extracted`` (facts collected so far), ``evidence_notes`` (cached one-line
    descriptions of uploads), ``credentials`` (case id + secret key held ONLY until the reporter confirms
    they saved them, so a lost HTTP response cannot lock them out of their own case).
    """

    __tablename__ = "report_state_tracking"

    report_id = Column(Uuid(as_uuid=True), ForeignKey("reports.id"), primary_key=True)
    current_step = Column(String(50), nullable=False)
    context_data = Column(JSON, default=dict, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=_now, onupdate=_now, nullable=False)

    report = relationship("Report", back_populates="state_tracking")


class Evidence(Base):
    __tablename__ = "evidence"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    report_id = Column(Uuid(as_uuid=True), ForeignKey("reports.id"), nullable=False, index=True)
    case_id = Column(String(15), nullable=True, index=True)  # filled in when the report is submitted

    file_path = Column(String(512), nullable=False)  # storage reference, e.g. "supastorage://evidence/reports/<id>/<uuid>.png"
    file_name = Column(String(255), nullable=False)  # sanitised display name
    mime_type = Column(String(100), nullable=False)  # sniffed from the bytes, not trusted from the client
    size_bytes = Column(Integer, nullable=False)
    file_hash = Column(String(128), nullable=False)

    forensic_analysis = Column(JSON, nullable=True)  # cached AI analysis of the file (see EvidenceProcessor)
    forensic_audio_analysis = Column(JSON, nullable=True)
    object_labels = Column(JSON, default=list)

    is_scanned = Column(Boolean, default=False, nullable=False)
    is_pii_cleansed = Column(Boolean, default=True, nullable=False)  # legacy flag
    uploaded_at = Column(DateTime(timezone=True), default=_now, nullable=False)

    report = relationship("Report", back_populates="evidence")
