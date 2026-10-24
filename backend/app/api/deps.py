"""Shared FastAPI dependencies."""

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

from app.core.config import settings
from app.core.security import admin_subject, decode_access_token

oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.API_V1_STR}/admin/auth/login")


async def get_current_admin(token: str = Depends(oauth2_scheme)) -> str:
    """Validate the admin JWT and return the administrator's username."""
    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        subject = str(decode_access_token(token)["sub"])
    except (jwt.InvalidTokenError, KeyError):
        raise unauthorized from None
    if subject != admin_subject():
        raise unauthorized
    return subject
