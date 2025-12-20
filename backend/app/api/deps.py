from typing import Generator, Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import ValidationError

from app.db.session import get_db
from app.core import security
from app.core.config import settings
from app.models.admin import Admin
from app.schemas.admin import TokenPayload

reusable_oauth2 = OAuth2PasswordBearer(
    tokenUrl=f"{settings.API_V1_STR}/admin/auth/login"
)

async def get_current_admin(
    db: AsyncSession = Depends(get_db),
    token: str = Depends(reusable_oauth2)
) -> Admin:
    try:
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[security.ALGORITHM]
        )
        token_data = TokenPayload(**payload)
    except (JWTError, ValidationError):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Could not validate credentials",
        )
    
    # query = select(Admin).where(Admin.id == token_data.sub) # UUID issue potentially if sub is string?
    # Ensure UUID conversion if needed
    try:
        admin_id = token_data.sub
    except Exception:
        raise HTTPException(status_code=403, detail="Invalid token subject")

    result = await db.execute(select(Admin).where(Admin.id == admin_id))
    admin = result.scalar_one_or_none()
    
    if not admin:
        raise HTTPException(status_code=404, detail="User not found")
    if not admin.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
        
    return admin

def get_current_active_superuser(
    current_admin: Admin = Depends(get_current_admin),
) -> Admin:
    if current_admin.role != "SUPER_ADMIN":
        raise HTTPException(
            status_code=400, detail="The user doesn't have enough privileges"
        )
    return current_admin
