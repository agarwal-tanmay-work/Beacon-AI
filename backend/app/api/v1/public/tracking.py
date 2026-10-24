"""Case follow-up for the reporter: status, investigator updates, and a two-way message channel."""

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.uploads import store_upload, validate_upload
from app.core.exceptions import AppError
from app.core.rate_limit import enforce
from app.db.session import get_db
from app.models.beacon import Beacon
from app.models.beacon_message import BeaconMessage
from app.models.beacon_update import BeaconUpdate
from app.schemas.report import (
    MessageAttachment,
    PublicUpdate,
    SecureUploadResponse,
    TrackMessage,
    TrackMessageRequest,
    TrackStatusRequest,
    TrackStatusResponse,
)
from app.services.case_access import authenticate_case
from app.services.storage_service import StorageService, ref_in_folder

router = APIRouter()


def message_to_schema(message: BeaconMessage) -> TrackMessage:
    """Attachments leave the API as short-lived signed links, never as storage references or public URLs."""
    return TrackMessage(
        id=str(message.id),
        sender_role=message.sender_role,  # type: ignore[arg-type]
        content=message.content,
        attachments=[
            MessageAttachment(
                file_name=att.get("file_name", "file"),
                file_path=StorageService.signed_path(att.get("file_path", "")),
                mime_type=att.get("mime_type", "application/octet-stream"),
            )
            for att in (message.attachments or [])
        ],
        timestamp=message.created_at,
    )


def validate_attachments(attachments: list[MessageAttachment], allowed_folder: str) -> list[dict[str, str]]:
    """Only files that were uploaded through this case's own upload endpoint may be attached to its messages."""
    checked = []
    for attachment in attachments:
        if not ref_in_folder(attachment.file_path, allowed_folder):
            raise AppError(422, "invalid_attachment", "One of the attachments is not valid. Please upload it again.")
        checked.append(attachment.model_dump())
    return checked


@router.post("/track", response_model=TrackStatusResponse)
async def track_case(payload: TrackStatusRequest, request: Request, db: AsyncSession = Depends(get_db)) -> TrackStatusResponse:
    enforce("track", request)
    case = await authenticate_case(db, request, payload.case_id, payload.secret_key)

    updates = (
        (await db.execute(select(BeaconUpdate).where(BeaconUpdate.case_id == case.case_id).order_by(BeaconUpdate.created_at)))
        .scalars()
        .all()
    )
    messages = (
        (await db.execute(select(BeaconMessage).where(BeaconMessage.case_id == case.case_id).order_by(BeaconMessage.created_at)))
        .scalars()
        .all()
    )

    return TrackStatusResponse(
        status="Pending" if case.status == "Received" else case.status,
        reported_at=case.reported_at,
        incident_summary=case.ai_summary or case.incident_summary,
        last_updated=case.last_updated_at,
        updates=[PublicUpdate(message=update.public_update, timestamp=update.created_at) for update in updates],
        messages=[message_to_schema(message) for message in messages],
    )


@router.post("/track/message", response_model=TrackMessage)
async def send_message(payload: TrackMessageRequest, request: Request, db: AsyncSession = Depends(get_db)) -> TrackMessage:
    enforce("track_write", request)
    case = await authenticate_case(db, request, payload.case_id, payload.secret_key)
    if not payload.content and not payload.attachments:
        raise AppError(422, "empty_message", "Please write a message or attach a file.")
    attachments = validate_attachments(payload.attachments, f"track/{case.case_id}")

    message = BeaconMessage(case_id=case.case_id, sender_role="user", content=payload.content, attachments=attachments)
    db.add(message)
    await db.commit()
    return message_to_schema(message)


@router.post("/track/upload", response_model=SecureUploadResponse)
async def upload_file(
    request: Request,
    case_id: str = Form(...),
    secret_key: str = Form(...),
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
) -> SecureUploadResponse:
    enforce("upload", request)
    case: Beacon = await authenticate_case(db, request, case_id, secret_key)
    upload = await validate_upload(file)
    stored = await store_upload(upload, f"track/{case.case_id}")
    return SecureUploadResponse(
        file_name=upload.display_name, file_path=stored.ref, mime_type=upload.detected.mime, size_bytes=len(upload.content)
    )
