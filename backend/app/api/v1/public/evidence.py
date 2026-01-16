from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
import os
import uuid
import hashlib
from app.db.local_db import LocalAsyncSession
from app.models.local_models import LocalEvidence
from app.core.config import settings
from app.services.storage_service import StorageService
from datetime import datetime, timezone

router = APIRouter()

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

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
        
        # Save to local uploads folder
        file_ext = os.path.splitext(file.filename)[1]
        unique_filename = f"{uuid.uuid4()}{file_ext}"
        file_path = ""
        
        # PRODUCTION: Upload to Supabase Storage if configured
        if settings.SUPABASE_URL and settings.SUPABASE_KEY and settings.ENVIRONMENT != "local_dev":
            try:
                # Use standardized StorageService
                upload_res = await StorageService.upload_file(content, file.filename, file.content_type or "application/octet-stream")
                file_path = f"supastorage://{upload_res['bucket']}/{upload_res['path']}"
                print(f"[UPLOAD] Uploaded to Supabase: {file_path}")
            except Exception as sup_err:
                print(f"[UPLOAD] Supabase Upload Failed: {sup_err}. Falling back to local.")
                # Fallback to local
                local_path = os.path.join(UPLOAD_DIR, unique_filename)
                with open(local_path, "wb") as f:
                    f.write(content)
                file_path = os.path.abspath(local_path)
        else:
            # DEV: Local Storage
            local_path = os.path.join(UPLOAD_DIR, unique_filename)
            with open(local_path, "wb") as f:
                f.write(content)
            file_path = os.path.abspath(local_path)
            
        # Track in local SQLite
        async with LocalAsyncSession() as session:
            # Only apply abspath if it's a local file path
            final_path = file_path
            if not file_path.startswith("supastorage://"):
                final_path = os.path.abspath(file_path)

            new_evidence = LocalEvidence(
                id=str(uuid.uuid4()),
                session_id=report_id,
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
