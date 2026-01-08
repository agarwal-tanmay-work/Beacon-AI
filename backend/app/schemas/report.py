from pydantic import BaseModel, Field, validator
from typing import Optional, List, Dict, Any
from uuid import UUID
from datetime import datetime
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
    timestamp: datetime
    next_step: Optional[str] = None
    case_id: Optional[str] = None  # BCN + 12 digits, present when submitted
    secret_key: Optional[str] = None # Present ONLY once on submission

class TrackStatusRequest(BaseModel):
    case_id: str
    secret_key: str

class TrackStatusResponse(BaseModel):
    status: str
    last_updated: datetime
    public_update: Optional[str] = None

class NGOUpdateRequest(BaseModel):
    raw_update: str
    updated_by: Optional[str] = "NGO_ADMIN"

class NGOUpdateResponse(BaseModel):
    status: str
    public_update: str
    timestamp: datetime

