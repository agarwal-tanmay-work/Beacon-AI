"""
Evidence Upload API.

Stores evidence records in LOCAL SQLite during chat.
Files are stored locally in uploads/ folder.
On case submission, files are encoded as Base64 and stored in beacon.evidence_files.
"""

from fastapi import APIRouter, UploadFile, File, Form, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.db.session import get_db
from app.db.local_db import LocalAsyncSession
from app.models.local_models import LocalSession, LocalEvidence
from app.services.media_service import MediaCleaner
import hashlib
import uuid
import os
import traceback

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
    1. Validate Token against LOCAL SQLite.
    2. Clean File (Strip Metadata, Blur Faces).
    3. Save Cleaned File locally.
    4. Record in LOCAL SQLite.
    
    Files are transferred to Supabase beacon table on case submission.
    """
    # 1. Auth - Validate against LOCAL DB
    try:
        session_uuid = uuid.UUID(report_id)
        session_id = str(session_uuid)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid Report ID format")

    input_hash = hashlib.sha256(access_token.encode()).hexdigest()
    
    async with LocalAsyncSession() as local_session:
        try:
            stmt = select(LocalSession).where(
                LocalSession.id == session_id, 
                LocalSession.access_token_hash == input_hash
            )
            result = await local_session.execute(stmt)
            session = result.scalar_one_or_none()
        except Exception as e:
            print(f"Error querying session: {e}")
            traceback.print_exc()
            raise HTTPException(status_code=500, detail="Database Error during Auth")
        
        if not session:
            raise HTTPException(status_code=401, detail="Invalid session")
        
        if not session.is_active:
            raise HTTPException(status_code=400, detail="Session is closed")
        
        if session.is_submitted:
            raise HTTPException(status_code=400, detail="Report already submitted")

        # 1b. Strict Cumulative Size Check (Max 5MB)
        MAX_TOTAL_SIZE_MB = 5
        MAX_TOTAL_BYTES = MAX_TOTAL_SIZE_MB * 1024 * 1024

        # Get current total size from local evidence
        try:
            size_stmt = select(LocalEvidence.size_bytes).where(LocalEvidence.session_id == session_id)
            size_res = await local_session.execute(size_stmt)
            current_sizes = size_res.scalars().all()
            current_total = sum(current_sizes)
        except Exception as e:
            print(f"Error checking size: {e}")
            traceback.print_exc()
            raise HTTPException(status_code=500, detail="Error validating storage quota")

        # Check new file size
        file_size_approx = file.size if file.size else 0
        if current_total + file_size_approx > MAX_TOTAL_BYTES:
            raise HTTPException(status_code=413, detail=f"Total upload limit of {MAX_TOTAL_SIZE_MB}MB exceeded.")

        # 2. Read & Clean
        try:
            content = await file.read()
            
            # Double check actual size after reading
            if current_total + len(content) > MAX_TOTAL_BYTES:
                raise HTTPException(status_code=413, detail=f"Total upload limit of {MAX_TOTAL_SIZE_MB}MB exceeded.")
            
            # Determine strict type
            cleaned_content = content
            
            # Preserve extension logic
            ext = os.path.splitext(file.filename)[1].lower()
            if not ext:
                # Fallback based on content type
                if file.content_type == "application/pdf": ext = ".pdf"
                elif file.content_type == "text/plain": ext = ".txt"
                else: ext = ".bin"
                
            filename = f"{uuid.uuid4()}{ext}" 
            mime_type = file.content_type
            
            is_pii_cleansed = False
            
            # Optional: PII Scrubbing for Images
            if mime_type.startswith("image/"):
                try:
                    cleaned_content = MediaCleaner.clean_image(content)
                    is_pii_cleansed = True
                except Exception:
                    # If cleaning fails, store original but mark as uncleansed
                    pass
            
            # 3. Store file locally
            file_path = os.path.join(UPLOAD_DIR, filename)
            with open(file_path, "wb") as f:
                f.write(cleaned_content)
            
            # 4. Record in LOCAL SQLite
            file_hash = hashlib.sha256(cleaned_content).hexdigest()
            
            new_evidence = LocalEvidence(
                session_id=session_id,
                file_name=filename,
                file_path=file_path,
                file_hash=file_hash,
                mime_type=mime_type,
                size_bytes=len(cleaned_content),
                is_pii_cleansed=is_pii_cleansed
            )
            local_session.add(new_evidence)
            await local_session.commit()
            
            print(f"[EVIDENCE] Uploaded {filename} for session {session_id}")
            
            return {"status": "uploaded", "file_id": filename}

        except HTTPException as he:
            raise he
        except Exception as e:
            print(f"Upload processing error: {e}")
            traceback.print_exc()
            raise HTTPException(status_code=500, detail=f"Processing failed: {str(e)}")


@router.get("/list/{session_id}")
async def list_evidence(session_id: str, access_token: str):
    """
    List all evidence files for a session.
    """
    input_hash = hashlib.sha256(access_token.encode()).hexdigest()
    
    async with LocalAsyncSession() as local_session:
        # Verify session
        stmt = select(LocalSession).where(
            LocalSession.id == session_id, 
            LocalSession.access_token_hash == input_hash
        )
        result = await local_session.execute(stmt)
        session = result.scalar_one_or_none()
        
        if not session:
            raise HTTPException(status_code=401, detail="Invalid session")
        
        # Get evidence list
        ev_stmt = select(LocalEvidence).where(LocalEvidence.session_id == session_id)
        ev_result = await local_session.execute(ev_stmt)
        evidence = ev_result.scalars().all()
        
        return {
            "session_id": session_id,
            "evidence_count": len(evidence),
            "files": [
                {
                    "file_name": ev.file_name,
                    "mime_type": ev.mime_type,
                    "size_bytes": ev.size_bytes,
                    "uploaded_at": ev.uploaded_at.isoformat() if ev.uploaded_at else None
                }
                for ev in evidence
            ]
        }
