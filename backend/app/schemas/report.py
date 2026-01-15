from pydantic import BaseModel, Field, validator
from typing import Optional, List, Dict, Any
from uuid import UUID
from datetime import datetime, timezone
from app.models.report import ReportStatus, SenderType

class CreateReportRequest(BaseModel):
    """Initial request to start a report session"""
    client_seed: str = Field(..., description="Random seed from client for encryption/token generation uniqueness")

class ReportResponse(BaseModel):
    report_id: UUID
    access_token: str
    message: str

class MessageRequest(BaseModel):
    report_id: UUID
    access_token: str
    content: str

class MessageResponse(BaseModel):
    report_id: UUID
    sender: SenderType
    content: str
    timestamp: Any
    next_step: Optional[str] = None
    case_id: Optional[str] = None  # BCN + 12 digits, present when submitted
    secret_key: Optional[str] = None # Present ONLY once on submission

    @validator("timestamp", pre=True)
    def ensure_utc(cls, v):
        if isinstance(v, datetime):
            if v.tzinfo is None: v = v.replace(tzinfo=timezone.utc)
            return v.astimezone(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
        return v

class TrackStatusRequest(BaseModel):
    case_id: str
    secret_key: str

class PublicUpdate(BaseModel):
    message: str
    timestamp: Any

    @validator("timestamp", pre=True)
    def ensure_utc(cls, v):
        if isinstance(v, datetime):
            if v.tzinfo is None: v = v.replace(tzinfo=timezone.utc)
            return v.astimezone(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
        return v

class MessageAttachment(BaseModel):
    file_name: str
    file_path: str
    mime_type: str

class TrackMessage(BaseModel):
    id: str
    sender_role: str
    content: Optional[str] = None
    attachments: List[MessageAttachment] = []
    timestamp: Any

    @validator("timestamp", pre=True)
    def ensure_utc(cls, v):
        if isinstance(v, datetime):
            if v.tzinfo is None: v = v.replace(tzinfo=timezone.utc)
            return v.astimezone(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
        return v

class TrackStatusResponse(BaseModel):
    status: str
    reported_at: Any
    incident_summary: Optional[str] = None
    last_updated: Any
    updates: List[PublicUpdate] = []
    messages: List[TrackMessage] = []

    @validator("reported_at", "last_updated", pre=True)
    def ensure_utc(cls, v):
        if isinstance(v, datetime):
            if v.tzinfo is None: v = v.replace(tzinfo=timezone.utc)
            return v.astimezone(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
        return v

class TrackMessageRequest(BaseModel):
    case_id: str
    secret_key: str
    content: Optional[str] = None
    attachments: List[MessageAttachment] = []

class SecureUploadResponse(BaseModel):
    file_name: str
    file_path: str
    mime_type: str

class NGOUpdateRequest(BaseModel):
    raw_update: str
    updated_by: Optional[str] = "NGO_ADMIN"
    status: Optional[str] = None

class NGOUpdateResponse(BaseModel):
    status: str
    public_update: str
    timestamp: Any

    @validator("timestamp", pre=True)
    def ensure_utc(cls, v):
        if isinstance(v, datetime):
            if v.tzinfo is None: v = v.replace(tzinfo=timezone.utc)
            return v.astimezone(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
        return v

