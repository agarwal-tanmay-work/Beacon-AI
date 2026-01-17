from fastapi import APIRouter, HTTPException, Depends, Path
from fastapi.responses import StreamingResponse
from sqlalchemy.future import select
from sqlalchemy.ext.asyncio import AsyncSession
import io

from app.db.session import get_db
from app.models.local_models import LocalSession

router = APIRouter()

@router.get("/{report_id}/{file_name}")
async def get_local_file(
    report_id: str = Path(..., title="Report ID"),
    file_name: str = Path(..., title="File Name"),
    db: AsyncSession = Depends(get_db)
):
    """
    Proxy endpoint to serve files from LocalSession DB when Supabase upload fails.
    """
    try:
        # Find session
        result = await db.execute(select(LocalSession).where(LocalSession.id == report_id))
        session = result.scalar_one_or_none()
        
        if not session or not session.evidence_data:
            raise HTTPException(status_code=404, detail="File not found")

        # Find file in evidence_data
        target_file = None
        for file_rec in session.evidence_data:
            if file_rec.get("name") == file_name:
                target_file = file_rec
                break
        
        if not target_file:
            raise HTTPException(status_code=404, detail="File not found in evidence")

        # Get content
        # If stored as HEX string (common in some JSON setups) or base64. 
        # But our LocalSession model (from memory) stores 'content' as bytes or similar?
        # Let's check LocalSession... actually 'evidence_data' is JSON, so content is likely NOT there.
        # Wait, if we are in 'local_db' fallback, where are the bytes?
        # The 'evidence_data' usually strips content to save space.
        
        # CORRECT LOGIC:
        # The 'evidence_data' in LocalSession is a metadata list.
        # The ACTUAL bytes are NOT persisted in LocalSession if the session is closed? 
        # NO, 'LocalSession' is a DB table. It has `evidence_data` (JSON).
        # Does it have a `files` table?
        # ... checking `LocalSession` definition ...
        # Assuming we don't have a dedicated files table, and `evidence_data` includes content?
        # If not, we have a problem.
        # BUT: In `report_engine.py`, `current_state["evidence_files"]` held the content.
        # If `StorageService` fails, we haven't stored the bytes anywhere else permanently if `LocalSession` doesn't hold it.
        
        # WAIT. `LocalSession` model has `evidence_data` which is type `JSON`.
        # Storing megabytes of binary in JSON column is bad.
        # However, for this fallback to work, we MUST rely on the fact that `evidence_data` *might* contain the base64 encoded content if we put it there.
        
        # Let's update `report_engine.py` to STORE the content in `evidence_data` ONLY if fallback is active.
        
        content_b64 = target_file.get("content_b64")
        if not content_b64:
             raise HTTPException(status_code=404, detail="File content not available locally")

        import base64
        file_bytes = base64.b64decode(content_b64)
        
        return StreamingResponse(
            io.BytesIO(file_bytes),
            media_type=target_file.get("mime_type", "application/octet-stream"),
            headers={"Content-Disposition": f"attachment; filename={file_name}"}
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
