from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import UUID4
import os

from app.db.session import get_db
from app.api import deps
from app.models.report import Evidence
from app.models.admin import Admin

router = APIRouter()

@router.get("/{evidence_id}/download")
async def download_evidence(
    evidence_id: UUID4,
    db: AsyncSession = Depends(get_db),
    current_admin: Admin = Depends(deps.get_current_admin),
):
    """
    Secure file download for Admins Only.
    """
    stmt = select(Evidence).where(Evidence.id == evidence_id)
    result = await db.execute(stmt)
    evidence = result.scalar_one_or_none()
    
    if not evidence:
        raise HTTPException(status_code=404, detail="Evidence not found")
    
    # Locate file
    # Assuming local storage as per Upload implementation
    file_path = os.path.join("uploads", evidence.file_name) # Security risk if filename traversal? 
    # db value `file_name` comes from UUID in upload endpoint 
    # (upload endpoint: `filename = f"{uuid.uuid4()}.jpg"`) -> SAFE.
    
    if not os.path.exists(file_path):
         raise HTTPException(status_code=404, detail="File on disk not found")
         
    return FileResponse(file_path, media_type=evidence.mime_type, filename=evidence.file_name)
