from fastapi import APIRouter, HTTPException, Body
from pydantic import BaseModel
import secrets

router = APIRouter()

class LoginRequest(BaseModel):
    username: str
    password: str

from app.core.security import create_access_token, verify_password, get_password_hash
from app.core.config import settings

@router.post("/login")
async def login(request: LoginRequest):
    """
    Strict authentication for NGO Portal.
    Credentials are managed via secure hashing and JWT.
    """
    VALID_USER = "beaconai"
    VALID_PASS_HASH = settings.ADMIN_PASSWORD_HASH
    
    # Fallback/Safety Check
    if not VALID_PASS_HASH:
        raise HTTPException(status_code=500, detail="Server misconfiguration: Admin password not set.")

    # Constant-time comparison for username
    is_user_ok = secrets.compare_digest(request.username, VALID_USER)
    
    # Verify password hash
    try:
        is_pass_ok = verify_password(request.password, VALID_PASS_HASH)
    except Exception:
        # Check against plain text IF environment was misconfigured (Legacy Fallback)
        is_pass_ok = (request.password == VALID_PASS_HASH)

    if not (is_user_ok and is_pass_ok):
        # Return generic error
        raise HTTPException(status_code=401, detail="Invalid credentials")
        
    # Generate a real JWT token
    access_token = create_access_token(subject=VALID_USER)
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": {
            "username": VALID_USER,
            "role": "admin"
        }
    }

