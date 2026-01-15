"""
Beacon Message Model - Stores two-way communication for a case.
"""

import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Text, DateTime, ForeignKey, JSON
from sqlalchemy.dialects.postgresql import UUID
from app.db.base import Base

class BeaconMessage(Base):
    """
    Stores messages exchanged between User vs NGO.
    """
    __tablename__ = "beacon_message"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    case_id = Column(String, ForeignKey("beacon.case_id"), nullable=False, index=True)
    
    sender_role = Column(String, nullable=False) # 'user' or 'ngo'
    content = Column(Text, nullable=True)        # Text content
    
    # Attachments: List of {file_name, file_path, file_hash, mime_type}
    attachments = Column(JSON, default=list)
    
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
