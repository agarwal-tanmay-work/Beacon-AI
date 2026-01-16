from fastapi import APIRouter, Depends, HTTPException
from fastapi.concurrency import run_in_threadpool
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from sqlalchemy.orm import load_only
from app.db.session import get_db
from app.models.beacon import Beacon
from app.models.beacon_message import BeaconMessage
from app.models.beacon_update import BeaconUpdate
from app.schemas.report import TrackStatusRequest, TrackStatusResponse, TrackMessageRequest, TrackMessage, MessageAttachment, SecureUploadResponse
from app.core.security import verify_password
import logging
import sys
import os
import uuid
import hashlib
from typing import List
from fastapi import UploadFile, File, Form
from app.core.config import settings

router = APIRouter()
logger = logging.getLogger(__name__)

@router.post("/track", response_model=TrackStatusResponse)
async def track_case(
    request: TrackStatusRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Track case status using Case ID and Secret Access Key.
    """
    print(f"\n[TRACK] START: case_id={request.case_id}", file=sys.stderr, flush=True)
    logger.info(f"Tracking request for case_id: {request.case_id}")
    
    try:
        # 1. Fetch Case
        # Optimization: Only load fields needed for auth and status
        print(f"[TRACK] 1. Executing DB query...", file=sys.stderr, flush=True)
        stmt = select(Beacon).options(
            load_only(
                Beacon.case_id,
                Beacon.secret_key,
                Beacon.secret_key_hash,
                Beacon.status,
                Beacon.reported_at,
                Beacon.incident_summary,
                Beacon.last_updated_at,
                Beacon.last_framed_status
            )
        ).where(Beacon.case_id == request.case_id)
        
        result = await db.execute(stmt)
        case = result.scalar_one_or_none()
        print(f"[TRACK] 2. DB query returned: {'Found' if case else 'Not Found'}", file=sys.stderr, flush=True)
        
        # GENERIC ERROR for security (don't reveal if ID exists)
        generic_error = HTTPException(status_code=401, detail="Invalid Case ID or Secret Key")
        
        if not case:
            logger.warning(f"Case ID not found: {request.case_id}")
            raise generic_error
            
        # 2. Verify Secret Key
        print(f"[TRACK] 3. Verifying secret key...", file=sys.stderr, flush=True)
        # We allow tracking via the visible plain secret_key 
        is_verified = False
        if case.secret_key and case.secret_key == request.secret_key:
            print(f"[TRACK] 4a. Plain key match", file=sys.stderr, flush=True)
            is_verified = True
        else:
            # Fallback check against hash if plain mismatch (handles legacy/migration)
            if case.secret_key_hash:
                print(f"[TRACK] 4b. No plain match, checking hash (non-blocking)...", file=sys.stderr, flush=True)
                is_verified = await run_in_threadpool(verify_password, request.secret_key, case.secret_key_hash)
            else:
                print(f"[TRACK] 4c. No plain match and no hash available", file=sys.stderr, flush=True)

        if not is_verified:
            print(f"[TRACK] 5. Verification FAILED", file=sys.stderr, flush=True)
            logger.warning(f"Invalid secret key for case_id: {request.case_id}")
            raise generic_error
            
        # 3. Fetch Updates
        print(f"[TRACK] 6. Fetching updates for case_id={request.case_id}...", file=sys.stderr, flush=True)
        # Sort chronologically (Oldest -> Newest) as requested
        updates_stmt = select(BeaconUpdate).where(
            BeaconUpdate.case_id == request.case_id
        ).order_by(BeaconUpdate.created_at.asc())
        
        updates_result = await db.execute(updates_stmt)
        updates = updates_result.scalars().all()
        print(f"[TRACK] 7. Found {len(updates)} updates", file=sys.stderr, flush=True)
        
        # Logic: Respect existing status unless it's the raw default "Received" AND no updates exist
        display_status = case.status
        if display_status == "Received" and not updates:
            display_status = "Pending"
        
        print(f"[TRACK] 8. Fetching messages...", file=sys.stderr, flush=True)
        # 4. Fetch Messages (Two-Way Communication)
        messages_stmt = select(BeaconMessage).where(
            BeaconMessage.case_id == request.case_id
        ).order_by(BeaconMessage.created_at.asc())
        
        try:
            messages_result = await db.execute(messages_stmt)
            messages = messages_result.scalars().all()
            print(f"[TRACK] 9. Found {len(messages)} messages", file=sys.stderr, flush=True)
        except Exception as msg_e:
            print(f"[TRACK] 9. ERROR fetching messages (likely table missing): {msg_e}", file=sys.stderr, flush=True)
            messages = []

        # 5. Return Latest Status, Updates, and Messages
        print(f"[TRACK] 10. Returning response", file=sys.stderr, flush=True)
        from app.schemas.report import PublicUpdate
        
        return TrackStatusResponse(
            status=display_status,
            reported_at=case.reported_at,
            incident_summary=case.incident_summary,
            last_updated=case.last_updated_at,
            updates=[
                PublicUpdate(
                    message=upd.public_update,
                    timestamp=upd.created_at
                ) for upd in updates
            ],
            messages=[
                TrackMessage(
                    id=str(msg.id),
                    sender_role=msg.sender_role,
                    content=msg.content,
                    attachments=[
                        MessageAttachment(
                            file_name=att.get("file_name"),
                            file_path=att.get("file_path", "").replace("\\", "/"),
                            mime_type=att.get("mime_type")
                        ) for att in (msg.attachments or [])
                    ],
                    timestamp=msg.created_at
                ) for msg in messages
            ]
        )
    except Exception as e:
        print(f"[TRACK] ERROR: {str(e)}", file=sys.stderr, flush=True)
        if isinstance(e, HTTPException):
            raise e
        logger.error(f"Tracking error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error during tracking")



@router.post("/track/message", response_model=TrackMessage)
async def send_message(
    request: TrackMessageRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Send a message from the user to the NGO (attached to a case).
    """
    # 1. Verify Auth (Inline for now to avoid dependency circles)
    stmt = select(Beacon).options(load_only(Beacon.case_id, Beacon.secret_key, Beacon.secret_key_hash)).where(Beacon.case_id == request.case_id)
    result = await db.execute(stmt)
    case = result.scalar_one_or_none()
    
    if not case:
        raise HTTPException(status_code=401, detail="Invalid Case ID")
        
    is_verified = False
    if case.secret_key and case.secret_key == request.secret_key:
        is_verified = True
    elif case.secret_key_hash:
        is_verified = await run_in_threadpool(verify_password, request.secret_key, case.secret_key_hash)
        
    if not is_verified:
        raise HTTPException(status_code=401, detail="Invalid Secret Key")

    # 2. Save Message
    try:
        new_message = BeaconMessage(
            case_id=request.case_id,
            sender_role="user",
            content=request.content,
            attachments=[att.model_dump() for att in request.attachments]
        )
        db.add(new_message)
        await db.commit()
        await db.refresh(new_message)
        return TrackMessage(
            id=str(new_message.id),
            sender_role=new_message.sender_role,
            content=new_message.content,
            attachments=[
                MessageAttachment(
                    file_name=att.get("file_name"),
                    file_path=att.get("file_path", "").replace("\\", "/"),
                    mime_type=att.get("mime_type")
                ) for att in (new_message.attachments or [])
            ],
            timestamp=new_message.created_at
        )
    except Exception as e:
        logger.error(f"Message send error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to send message")

@router.post("/track/upload", response_model=SecureUploadResponse)
async def upload_track_file(
    case_id: str = Form(...),
    secret_key: str = Form(...),
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db)
):
    """
    Upload a file for the track page chat.
    """
    # 1. Verify Auth
    stmt = select(Beacon).options(load_only(Beacon.case_id, Beacon.secret_key, Beacon.secret_key_hash)).where(Beacon.case_id == case_id)
    result = await db.execute(stmt)
    case = result.scalar_one_or_none()
    
    if not case:
        raise HTTPException(status_code=401, detail="Invalid Case ID")
        
    is_verified = False
    if case.secret_key and case.secret_key == secret_key:
        is_verified = True
    elif case.secret_key_hash:
        is_verified = await run_in_threadpool(verify_password, secret_key, case.secret_key_hash)
        
    if not is_verified:
        raise HTTPException(status_code=401, detail="Invalid Secret Key")

    # 2. Save File
    try:
        from app.services.storage_service import StorageService
        UPLOAD_DIR = "uploads"
        os.makedirs(UPLOAD_DIR, exist_ok=True)
        
        content = await file.read()
        file_ext = os.path.splitext(file.filename)[1]
        unique_filename = f"{uuid.uuid4()}{file_ext}"
        file_path = ""

        # Production Upload
        if settings.SUPABASE_URL and settings.SUPABASE_KEY and settings.ENVIRONMENT != "local_dev":
            try:
                upload_res = await StorageService.upload_file(content, file.filename, file.content_type or "application/octet-stream")
                file_path = f"supastorage://{upload_res['bucket']}/{upload_res['path']}"
            except Exception as e:
                logger.error(f"Supabase upload failed, falling back to local: {e}")
        
        if not file_path:
            local_path = os.path.join(UPLOAD_DIR, unique_filename).replace("\\", "/")
            with open(local_path, "wb") as f:
                f.write(content)
            file_path = local_path
            
        return SecureUploadResponse(
            file_name=file.filename,
            file_path=file_path,
            mime_type=file.content_type or "application/octet-stream"
        )
    except Exception as e:
        logger.error(f"Track upload error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
