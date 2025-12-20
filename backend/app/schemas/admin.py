from pydantic import BaseModel, EmailStr
from typing import Optional
from uuid import UUID
from datetime import datetime
from app.models.admin import AdminRole

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenPayload(BaseModel):
    sub: Optional[str] = None

class AdminLogin(BaseModel):
    email: EmailStr
    password: str

class AdminResponse(BaseModel):
    id: UUID
    email: EmailStr
    role: AdminRole
    is_active: bool

class AdminCreate(BaseModel):
    email: EmailStr
    password: str
    role: AdminRole = AdminRole.MODERATOR
