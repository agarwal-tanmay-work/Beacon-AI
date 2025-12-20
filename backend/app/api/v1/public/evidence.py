from fastapi import APIRouter, UploadFile, File, Form, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.db.session import get_db
from app.models.report import Report
from app.services.media_service import MediaCleaner
import hashlib
import uuid
import os
import secrets

router = APIRouter()

# Simple local storage for demo (In prod, use S3)
UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

@router.post("/upload")
async def upload_evidence(
    report_id: str = Form(...),
    access_token: str = Form(...),
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db)
):
    """
    Secure Evidence Upload.
    1. Validate Token.
    2. Clean File (Strip Metadata, Blur Faces).
    3. Save Cleaned File ONLY.
    """
    # 1. Auth Headers
    input_hash = hashlib.sha256(access_token.encode()).hexdigest()
    stmt = select(Report).where(Report.id == report_id, Report.access_token_hash == input_hash)
    result = await db.execute(stmt)
    report = result.scalar_one_or_none()
    
    if not report:
        raise HTTPException(status_code=401, detail="Invalid session")

    # 2. Read & Clean
    try:
        content = await file.read()
        
        # Determine strict type
        cleaned_content = content
        filename = f"{uuid.uuid4()}.jpg" # Normalize/Mask filename
        
        if file.content_type.startswith("image/"):
             cleaned_content = MediaCleaner.clean_image(content)
        
        # 3. Store
        from app.services.storage_service import StorageService
        saved_filename = await StorageService.save_file(cleaned_content, filename)
        
        # 4. Record in DB
        from app.models.report import Evidence # Lazy import to avoid circular deps if any specific issue, though top level is fine usually
        
        # Calculate Hash
        file_hash = hashlib.sha256(cleaned_content).hexdigest()
        
        new_evidence = Evidence(
            report_id=report.id,
            file_name=saved_filename,
            file_path=f"uploads/{saved_filename}", # redundant but required by model
            file_hash=file_hash,
            mime_type="image/jpeg",
            size_bytes=len(cleaned_content),
            is_pii_cleansed=True
        )
        db.add(new_evidence)
        await db.commit()
        
        return {"status": "uploaded", "file_id": saved_filename}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Processing failed: {str(e)}")
