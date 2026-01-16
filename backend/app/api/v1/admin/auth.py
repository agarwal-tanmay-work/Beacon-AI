from fastapi import APIRouter, HTTPException, Body
from pydantic import BaseModel
import secrets
import logging

router = APIRouter()
logger = logging.getLogger(__name__)

class LoginRequest(BaseModel):
    username: str
    password: str

from app.core.security import create_access_token, verify_password, get_password_hash
from app.core.config import settings

@router.post("/login")
async def login(request: LoginRequest):
    """
    Deterministic Admin Authentication.
    Matches username 'beaconai' and either:
    1. ADMIN_PASSWORD_HASH (if set)
    2. 'BeaconAI@26' (fallback if hash not set)
    """
    VALID_USER = "beaconai"
    FALLBACK_PASS = "BeaconAI@26"
    
    # 1. Flexible Username Check (Case-insensitive + Alias)
    input_user = request.username.lower().strip()
    if input_user not in [VALID_USER, "admin"]:
        print(f"[AUTH] Login failed: Username '{input_user}' not recognized.")
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    is_verified = False
    
    # 2. Determine Auth Method
    if settings.ADMIN_PASSWORD_HASH and settings.ADMIN_PASSWORD_HASH.strip():
        # Path A: Hash-based Verification (Production)
        print(f"[AUTH] Method: HASH (Prefix: {settings.ADMIN_PASSWORD_HASH[:10]}...)")
        try:
            from app.core.security import verify_password
            from fastapi.concurrency import run_in_threadpool
            
            # Run CPU-intensive hashing in threadpool
            is_verified = await run_in_threadpool(verify_password, request.password, settings.ADMIN_PASSWORD_HASH)
            if not is_verified:
                 print("[AUTH] Hash verification failed.")
        except Exception as e:
            print(f"[AUTH] Error verifying hash: {e}")
            is_verified = False
    else:
        # Path B: Plaintext Fallback (Dev/Recovery)
        print("[AUTH] Method: FALLBACK (Plaintext)")
        if request.password == FALLBACK_PASS:
            is_verified = True
        else:
             print("[AUTH] Fallback password mismatch.")

    if not is_verified:
        raise HTTPException(status_code=401, detail="Invalid credentials")
        
    print(f"[AUTH] Login SUCCESS for user: {VALID_USER}")
        
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

