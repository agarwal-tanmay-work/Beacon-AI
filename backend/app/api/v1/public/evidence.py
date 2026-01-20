from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
import os
import uuid
import hashlib
from app.core.config import settings
from app.services.storage_service import StorageService
from datetime import datetime, timezone

router = APIRouter()

# Cloud-Only Storage (Supabase)
# No local uploads directory used in production.

@router.post("/upload")
async def upload_evidence(
    report_id: str = Form(...),
    access_token: str = Form(...),
    file: UploadFile = File(...)
):
    """
    Upload evidence file, save to local staging, and track in SQLite.
    """
    # Simple token validation (matching reporting.py logic)
    if not access_token.startswith("tk_"):
        raise HTTPException(status_code=401, detail="Invalid access token")

    try:
        content = await file.read()
        file_hash = hashlib.sha256(content).hexdigest()
        
        # PRODUCTION: Upload to Supabase Storage
        try:
            # Use standardized StorageService
            upload_res = await StorageService.upload_file(content, file.filename, file.content_type or "application/octet-stream")
            file_path = f"supastorage://{upload_res['bucket']}/{upload_res['path']}"
            print(f"[UPLOAD] Uploaded to Supabase: {file_path}")
        except Exception as sup_err:
            print(f"[UPLOAD] Supabase Upload Failed: {sup_err}")
            raise HTTPException(status_code=503, detail="Cloud storage unavailable. Please try again later.")
            
        # Track in Supabase
        from app.db.session import AsyncSessionLocal
        from app.models.report import Evidence
        
        async with AsyncSessionLocal() as session:
            # Only apply abspath if it's a local file path
            final_path = file_path
            if not file_path.startswith("supastorage://"):
                final_path = os.path.abspath(file_path)

            new_evidence = Evidence(
                id=uuid.uuid4(),
                report_id=uuid.UUID(report_id),
                file_name=file.filename,
                file_path=final_path,
                mime_type=file.content_type or "application/octet-stream",
                size_bytes=len(content),
                file_hash=file_hash,
                is_pii_cleansed=False,
                uploaded_at=datetime.now(timezone.utc)
            )
            session.add(new_evidence)
            await session.commit()
            
        return {
            "status": "success",
            "file_name": file.filename,
            "hash": file_hash
        }
    except Exception as e:
        import traceback
        print(f"Upload error: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))
