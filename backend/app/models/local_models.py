"""
Local SQLite Models for Staging Data.

These models store transient session data locally until case submission.
Only data needed by authorities is transferred to Supabase beacon table.
"""

import uuid
from datetime import datetime
from typing import Optional
from sqlalchemy import Column, String, Boolean, Integer, DateTime, Text, JSON, Enum
from sqlalchemy.orm import declarative_base
import enum

# Separate Base for local models
LocalBase = declarative_base()


class LocalSenderType(str, enum.Enum):
    USER = 'USER'
    AI = 'AI'
    SYSTEM = 'SYSTEM'


class LocalSession(LocalBase):
    """
    Active chat session stored locally.
    """
    __tablename__ = "local_sessions"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    access_token_hash = Column(String(255), unique=True, nullable=False, index=True)
    is_active = Column(Boolean, default=True, nullable=False)
    is_submitted = Column(Boolean, default=False, nullable=False)
    case_id = Column(String(15), nullable=True)  # Set when submitted
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class LocalConversation(LocalBase):
    """
    Chat messages stored locally during active session.
    """
    __tablename__ = "local_conversations"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id = Column(String(36), nullable=False, index=True)
    sender = Column(Enum(LocalSenderType), nullable=False)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class LocalStateTracking(LocalBase):
    """
    Session state tracking stored locally.
    """
    __tablename__ = "local_state_tracking"
    
    session_id = Column(String(36), primary_key=True)
    current_step = Column(String(50), nullable=False)
    context_data = Column(JSON, default=dict, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class LocalEvidence(LocalBase):
    """
    Evidence files stored locally before case submission.
    """
    __tablename__ = "local_evidence"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id = Column(String(36), nullable=False, index=True)
    file_name = Column(String(255), nullable=False)
    file_path = Column(String(512), nullable=False)
    mime_type = Column(String(100), nullable=False)
    size_bytes = Column(Integer, nullable=False)
    file_hash = Column(String(128), nullable=False)
    is_pii_cleansed = Column(Boolean, default=False, nullable=False)
    uploaded_at = Column(DateTime, default=datetime.utcnow, nullable=False)
