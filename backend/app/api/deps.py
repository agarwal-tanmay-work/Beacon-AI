from typing import Generator
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import ALGORITHM
from app.db.session import get_db

oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl=f"{settings.API_V1_STR}/admin/auth/login"
)

async def get_current_admin(
    token: str = Depends(oauth2_scheme)
) -> str:
    """
    Validate JWT token and return the subject (username).
    In this demo, we check against the hardcoded admin user.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[ALGORITHM]
        )
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    
    # Validation against hardcoded demo user
    if username != "beaconai":
        raise credentials_exception
    
    return username
