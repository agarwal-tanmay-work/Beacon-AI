from fastapi import APIRouter, HTTPException, Body
from pydantic import BaseModel
import secrets

router = APIRouter()

class LoginRequest(BaseModel):
    username: str
    password: str

@router.post("/login")
async def login(request: LoginRequest):
    """
    Strict authentication for NGO Portal.
    Credentials are hardcoded as per specific security requirements.
    """
    # Strict credential check - constant time comparison to prevent timing attacks
    # In a real database scenario we'd use hashes, but requirements specify "predefined credentials"
    
    VALID_USER = "beaconai"
    VALID_PASS = "BeaconAI@26"
    
    is_user_ok = secrets.compare_digest(request.username, VALID_USER)
    is_pass_ok = secrets.compare_digest(request.password, VALID_PASS)
    
    if not (is_user_ok and is_pass_ok):
        # Generic error message as requested
        raise HTTPException(status_code=401, detail="Invalid credentials")
        
    # Generate a simple session token (in a real app this would be a signed JWT)
    # For this closed demo loop, a random token works as the frontend just checks expected behavior
    token = secrets.token_urlsafe(32)
    
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {
            "username": VALID_USER,
            "role": "admin"
        }
    }
