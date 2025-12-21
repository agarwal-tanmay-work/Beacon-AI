import uuid
from datetime import datetime
from typing import Optional, List, Dict, Any
from sqlalchemy import Column, String, Boolean, Integer, DateTime, ForeignKey, Enum, Text, JSON
from sqlalchemy.dialects.postgresql import UUID # UUID is fine usually as string in SQLite or dedicated type if using aiosqlite? SQLAlchemy handles it. But JSONB is PG specific.
from sqlalchemy.orm import relationship
import enum

from app.db.base import Base

class ReportStatus(str, enum.Enum):
    NEW = 'NEW'
    ANALYZING = 'ANALYZING'
    VERIFIED = 'VERIFIED'
    IN_REVIEW = 'IN_REVIEW'
    ESCALATED = 'ESCALATED'
    CLOSED = 'CLOSED'
    DISMISSED = 'DISMISSED'

class ReportPriority(str, enum.Enum):
    LOW = 'LOW'
    MEDIUM = 'MEDIUM'
    HIGH = 'HIGH'
    CRITICAL = 'CRITICAL'

class SenderType(str, enum.Enum):
    USER = 'USER'
    AI = 'AI'
    SYSTEM = 'SYSTEM'

class Report(Base):
    __tablename__ = "reports"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    case_id = Column(String(15), unique=True, nullable=True, index=True)  # Format: BCN + 12 chars
    access_token_hash = Column(String(255), unique=True, nullable=False, index=True)
    
    status = Column(Enum(ReportStatus), default=ReportStatus.NEW, nullable=False, index=True)
    priority = Column(Enum(ReportPriority), default=ReportPriority.LOW, nullable=False, index=True)
    credibility_score = Column(Integer, nullable=True)
    credibility_breakdown = Column(JSON, nullable=True) # Full 8-dimension breakdown
    authority_summary = Column(Text, nullable=True)
    
    categories = Column(JSON, default=list)
    location_meta = Column(JSON, nullable=True)
    
    # New Credibility Analysis Fields
    incident_summary = Column(Text, nullable=True)
    evidence_analysis = Column(JSON, nullable=True)
    tone_analysis = Column(JSON, nullable=True)
    consistency_score = Column(Integer, nullable=True)
    fabrication_risk_score = Column(Integer, nullable=True)
    
    is_archived = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    conversations = relationship("ReportConversation", back_populates="report", cascade="all, delete-orphan")
    state_tracking = relationship("ReportStateTracking", back_populates="report", uselist=False, cascade="all, delete-orphan")
    evidence = relationship("Evidence", back_populates="report", cascade="all, delete-orphan")

class ReportConversation(Base):
    __tablename__ = "report_conversations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    report_id = Column(UUID(as_uuid=True), ForeignKey("reports.id"), nullable=False)
    sender = Column(Enum(SenderType), nullable=False)
    
    content_redacted = Column(Text, nullable=False)
    intent_detected = Column(String(100), nullable=True)
    
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)

    report = relationship("Report", back_populates="conversations")

class ReportStateTracking(Base):
    __tablename__ = "report_state_tracking"

    report_id = Column(UUID(as_uuid=True), ForeignKey("reports.id"), primary_key=True)
    current_step = Column(String(50), nullable=False)
    context_data = Column(JSON, default=dict, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


    report = relationship("Report", back_populates="state_tracking")

class Evidence(Base):
    __tablename__ = "evidence"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    report_id = Column(UUID(as_uuid=True), ForeignKey("reports.id"), nullable=False)
    
    file_path = Column(String(512), nullable=False)
    file_name = Column(String(255), nullable=False)
    mime_type = Column(String(100), nullable=False)
    size_bytes = Column(Integer, nullable=False)
    file_hash = Column(String(128), nullable=False)
    
    is_scanned = Column(Boolean, default=False, nullable=False)
    is_pii_cleansed = Column(Boolean, default=True, nullable=False)
    
    uploaded_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)

    report = relationship("Report", back_populates="evidence")
