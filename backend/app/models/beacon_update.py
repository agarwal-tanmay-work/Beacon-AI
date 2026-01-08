"""
Beacon Update Model - Stores updates for a case.
"""

import uuid
from datetime import datetime
from sqlalchemy import Column, String, Text, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from app.db.base import Base

class BeaconUpdate(Base):
    """
    Stores status updates for a beacon case.
    """
    __tablename__ = "beacon_update"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    case_id = Column(String, ForeignKey("beacon.case_id"), nullable=False, index=True)
    
    raw_update = Column(Text, nullable=False)    # Original text from NGO
    public_update = Column(Text, nullable=False) # LLM-rewritten text for public
    updated_by = Column(String, nullable=True)   # NGO User ID or Name
    
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
