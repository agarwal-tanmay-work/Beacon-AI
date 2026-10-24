"""Two-way messages between the reporter and the investigators of a case."""

import uuid
from datetime import UTC, datetime

from sqlalchemy import JSON, Column, DateTime, ForeignKey, String, Text, Uuid

from app.db.base import Base


def _now() -> datetime:
    return datetime.now(UTC)


class BeaconMessage(Base):
    __tablename__ = "beacon_message"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    case_id = Column(String, ForeignKey("beacon.case_id"), nullable=False, index=True)
    sender_role = Column(String, nullable=False)  # "user" | "admin"
    content = Column(Text, nullable=True)
    attachments = Column(JSON, default=list)  # [{"file_name", "file_path" (storage ref), "mime_type"}]
    created_at = Column(DateTime(timezone=True), default=_now, nullable=False)
