"""Public status updates published by investigators."""

import uuid
from datetime import UTC, datetime

from sqlalchemy import Column, DateTime, ForeignKey, String, Text, Uuid

from app.db.base import Base


def _now() -> datetime:
    return datetime.now(UTC)


class BeaconUpdate(Base):
    __tablename__ = "beacon_update"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    case_id = Column(String, ForeignKey("beacon.case_id"), nullable=False, index=True)
    raw_update = Column(Text, nullable=True)  # what the admin typed (internal)
    public_update = Column(Text, nullable=False)  # what the reporter sees
    updated_by = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), default=_now, nullable=False)
