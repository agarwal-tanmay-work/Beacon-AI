"""``beacon`` - the permanent record of a submitted case (exactly one row per case)."""

import uuid
from datetime import UTC, datetime

from sqlalchemy import JSON, Column, DateTime, Integer, String, Text, Uuid

from app.db.base import Base


def _now() -> datetime:
    return datetime.now(UTC)


class Beacon(Base):
    __tablename__ = "beacon"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    reported_at = Column(DateTime(timezone=True), nullable=False)
    case_id = Column(String(15), unique=True, nullable=False, index=True)  # BCN + 12 digits

    # What the reporter told us. ``incident_summary`` is a neutral paragraph built from the structured facts at
    # submission time; ``reporter_details`` keeps those facts (what/where/when/who + the *optional* contact info).
    incident_summary = Column(Text, nullable=True)
    reporter_details = Column(JSON, nullable=True)

    # Filled by background analysis (see ScoringService)
    ai_summary = Column(Text, nullable=True)
    ai_explanation = Column(JSON, nullable=True)
    credibility_score = Column(Integer, nullable=True)  # DB constraint: 1..100, NULL until scored
    score_explanation = Column(Text, nullable=True)
    analysis_status = Column(String, default="pending", nullable=False)  # pending | processing | completed | failed
    analysis_attempts = Column(Integer, default=0, nullable=False)
    analysis_last_error = Column(Text, nullable=True)  # operator diagnostics only, never sent to clients

    # Reporter access. Only a hash of the secret key is kept. ``secret_key`` is a LEGACY plaintext column that
    # older versions filled in; the maintenance job scrubs it (app.services.maintenance.scrub_plaintext_secret_keys).
    secret_key = Column(String(10), nullable=True)
    secret_key_hash = Column(String, nullable=True)

    status = Column(String, default="Received", nullable=False)  # Received/Pending | Ongoing | Completed
    last_raw_status = Column(Text, nullable=True)  # last admin update, as typed
    last_framed_status = Column(Text, nullable=True)  # ... and as published
    # Reporter-visible "last updated": set explicitly when an investigator acts. (No onupdate: background AI
    # analysis touches the row too, and that must not look like case progress.)
    last_updated_at = Column(DateTime(timezone=True), default=_now, nullable=False)

    # [{"file_name", "mime_type", "size_bytes", "file_path", + forensic fields after analysis}]
    evidence_files = Column(JSON, default=list)

    created_at = Column(DateTime(timezone=True), default=_now, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=_now, onupdate=_now, nullable=False)
