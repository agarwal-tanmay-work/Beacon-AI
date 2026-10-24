"""Case management for investigators."""

from typing import Any
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, File, Query, UploadFile
from pydantic import BaseModel
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import load_only

from app.api.deps import get_current_admin
from app.api.uploads import store_upload, validate_upload
from app.api.v1.public.tracking import message_to_schema, validate_attachments
from app.core.exceptions import AppError
from app.core.time_utils import utc_now
from app.db.session import get_db
from app.models.beacon import Beacon
from app.models.beacon_message import BeaconMessage
from app.models.beacon_update import BeaconUpdate
from app.models.report import Report
from app.schemas.report import (
    AdminMessageRequest,
    AdminReportSchema,
    CaseUpdateSchema,
    SecureUploadResponse,
    TrackMessage,
    UpdateStatusRequest,
    UTCDateTime,
)
from app.services.scoring_rules import confidence_band, priority_for
from app.services.scoring_service import ScoringService
from app.services.storage_service import StorageService

router = APIRouter(dependencies=[Depends(get_current_admin)])


class AdminReportListItem(BaseModel):
    id: UUID
    case_id: str
    status: str
    priority: str
    credibility_score: int | None = None
    confidence: str | None = None
    analysis_status: str | None = None
    created_at: UTCDateTime


def display_status(case: Beacon) -> str:
    return "Pending" if case.status == "Received" else case.status


def evidence_for_admin(entry: dict[str, Any]) -> dict[str, Any]:
    """Evidence record as shown to investigators: a short-lived signed link, never the storage reference."""
    ref = entry.get("file_path", "")
    return {
        "file_name": entry.get("file_name", "file"),
        "mime_type": entry.get("mime_type"),
        "size_bytes": entry.get("size_bytes", 0),
        "full_url": StorageService.signed_path(ref) if ref else None,
        "kind": entry.get("kind"),
        "summary": entry.get("summary"),
        "analyzed": entry.get("analyzed", False),
        "quality_notes": entry.get("quality_notes", []),
    }


def to_admin_schema(case: Beacon, updates: list[BeaconUpdate] | None = None) -> AdminReportSchema:
    score = case.credibility_score
    return AdminReportSchema(
        id=case.id,
        case_id=case.case_id,
        status=display_status(case),
        priority=priority_for(score),
        credibility_score=score,
        confidence=None if score is None else confidence_band(score),
        created_at=case.reported_at,
        incident_summary=case.incident_summary,
        ai_summary=case.ai_summary,
        ai_explanation=case.ai_explanation,
        analysis_status=case.analysis_status,
        app_score_explanation=case.score_explanation,
        reporter_details=case.reporter_details,
        evidence_files=[evidence_for_admin(e) for e in (case.evidence_files or [])],
        updates=[
            CaseUpdateSchema(id=str(u.id), public_update=u.public_update, created_at=u.created_at, updated_by="Admin")
            for u in (updates or [])
        ],
    )


async def get_case(db: AsyncSession, case_uuid: UUID) -> Beacon:
    case = await db.get(Beacon, case_uuid)
    if case is None:
        raise AppError(404, "case_not_found", "Case not found.")
    return case


@router.get("/", response_model=list[AdminReportListItem])
async def list_reports(
    limit: int = Query(default=300, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
) -> list[AdminReportListItem]:
    rows = (
        await db.execute(
            select(Beacon)
            .options(
                load_only(Beacon.id, Beacon.case_id, Beacon.status, Beacon.credibility_score, Beacon.analysis_status, Beacon.reported_at)
            )
            .order_by(desc(Beacon.reported_at))
            .limit(limit)
            .offset(offset)
        )
    ).scalars()
    return [
        AdminReportListItem(
            id=case.id,
            case_id=case.case_id,
            status=display_status(case),
            priority=priority_for(case.credibility_score),
            credibility_score=case.credibility_score,
            confidence=None if case.credibility_score is None else confidence_band(case.credibility_score),
            analysis_status=case.analysis_status,
            created_at=case.reported_at,
        )
        for case in rows
    ]


@router.get("/{case_uuid}", response_model=AdminReportSchema)
async def get_report(case_uuid: UUID, db: AsyncSession = Depends(get_db)) -> AdminReportSchema:
    case = await get_case(db, case_uuid)
    updates = (
        (await db.execute(select(BeaconUpdate).where(BeaconUpdate.case_id == case.case_id).order_by(BeaconUpdate.created_at)))
        .scalars()
        .all()
    )
    return to_admin_schema(case, list(updates))


@router.put("/{case_uuid}/status", response_model=AdminReportSchema)
async def update_status(case_uuid: UUID, payload: UpdateStatusRequest, db: AsyncSession = Depends(get_db)) -> AdminReportSchema:
    case = await get_case(db, case_uuid)
    case.status = payload.status
    case.last_updated_at = utc_now()
    await db.commit()
    return to_admin_schema(case)


@router.get("/{case_uuid}/messages", response_model=list[TrackMessage])
async def list_messages(case_uuid: UUID, db: AsyncSession = Depends(get_db)) -> list[TrackMessage]:
    case = await get_case(db, case_uuid)
    messages = (
        await db.execute(select(BeaconMessage).where(BeaconMessage.case_id == case.case_id).order_by(BeaconMessage.created_at))
    ).scalars()
    return [message_to_schema(m) for m in messages]


@router.post("/{case_uuid}/message", response_model=TrackMessage)
async def send_message(case_uuid: UUID, payload: AdminMessageRequest, db: AsyncSession = Depends(get_db)) -> TrackMessage:
    case = await get_case(db, case_uuid)
    if not payload.content and not payload.attachments:
        raise AppError(422, "empty_message", "Please write a message or attach a file.")
    attachments = validate_attachments(payload.attachments, f"admin/{case.case_id}")
    message = BeaconMessage(case_id=case.case_id, sender_role="admin", content=payload.content, attachments=attachments)
    db.add(message)
    case.last_updated_at = utc_now()
    await db.commit()
    return message_to_schema(message)


@router.post("/{case_uuid}/upload", response_model=SecureUploadResponse)
async def upload_file(case_uuid: UUID, file: UploadFile = File(...), db: AsyncSession = Depends(get_db)) -> SecureUploadResponse:
    case = await get_case(db, case_uuid)
    upload = await validate_upload(file)
    stored = await store_upload(upload, f"admin/{case.case_id}")
    return SecureUploadResponse(
        file_name=upload.display_name, file_path=stored.ref, mime_type=upload.detected.mime, size_bytes=len(upload.content)
    )


@router.post("/{case_uuid}/analyze", status_code=202)
async def reanalyze(case_uuid: UUID, background: BackgroundTasks, db: AsyncSession = Depends(get_db)) -> dict[str, str]:
    """Re-run the AI analysis (for cases that failed during an outage or on a retired model)."""
    case = await get_case(db, case_uuid)
    case_id = case.case_id
    if ScoringService.is_running(case_id):
        return {"message": "Analysis is already running for this case.", "case_id": case_id}

    report_id = (await db.execute(select(Report.id).where(Report.case_id == case_id))).scalar_one_or_none()
    if report_id is None:
        raise AppError(404, "session_not_found", "The original reporting session for this case could not be found.")

    case.analysis_status = "pending"
    case.analysis_attempts = 0
    await db.commit()
    background.add_task(ScoringService.run_background_scoring, str(report_id), case_id)
    return {"message": "Analysis queued.", "case_id": case_id}
