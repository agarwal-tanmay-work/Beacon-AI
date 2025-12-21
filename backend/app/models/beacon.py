"""
Beacon Model - Supabase Table for Final Case Storage.

This table stores exactly ONE row per case with:
- reported_at: When user first submits
- case_id: BCN + 12 digits (unique, immutable)
- incident_summary: Generated once after full chat
- credibility_score: Integer 1-100 (permanent)
- score_explanation: Detailed reasoning for the score
- evidence_files: JSONB with actual file content (Base64)
"""

import uuid
from datetime import datetime
from typing import Optional, List, Dict, Any
from sqlalchemy import Column, String, Integer, DateTime, Text, JSON
from sqlalchemy.dialects.postgresql import UUID
import re

from app.db.base import Base


class Beacon(Base):
    """
    Final case storage in Supabase.
    Exactly ONE row per case - INSERT once, UPDATE for subsequent changes.
    """
    __tablename__ = "beacon"
    
    # Primary Key
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Required Fields (set on initial INSERT)
    reported_at = Column(DateTime(timezone=True), nullable=False)
    case_id = Column(String(15), unique=True, nullable=False, index=True)
    
    # Generated Fields (set via UPDATE after background processing)
    incident_summary = Column(Text, nullable=True)
    credibility_score = Column(Integer, nullable=True)  # 1-100
    score_explanation = Column(Text, nullable=True)
    
    # Evidence (Base64 encoded files in JSONB)
    # Format: [{"file_name": "...", "mime_type": "...", "size_bytes": N, "content_base64": "..."}]
    evidence_files = Column(JSON, default=list)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Two-Phase Analysis Tracking
    analysis_status = Column(String, default="pending", nullable=False) # 'pending' or 'completed'
    analysis_attempts = Column(Integer, default=0, nullable=False)
    analysis_last_error = Column(Text, nullable=True) # Internal debugging only
    
    @staticmethod
    def validate_case_id(case_id: str) -> bool:
        """
        Validate case_id format: BCN + 12 digits.
        """
        if not case_id:
            return False
        pattern = r'^BCN\d{12}$'
        return bool(re.match(pattern, case_id))
    
    @staticmethod
    def validate_credibility_score(score: int) -> bool:
        """
        Validate credibility score is between 1 and 100.
        """
        return 1 <= score <= 100
