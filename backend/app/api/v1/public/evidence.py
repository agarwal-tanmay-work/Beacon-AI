"""Evidence upload for a reporting session."""

import uuid
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, UploadFile
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.uploads import store_upload, validate_upload
from app.core.config import settings
from app.core.exceptions import AppError
from app.core.rate_limit import limit
from app.db.session import get_db
from app.models.report import Evidence
from app.schemas.report import EvidenceUploadResponse
from app.services.report_engine import ReportEngine
from app.services.storage_service import StorageService

router = APIRouter()


@router.post("/upload", response_model=EvidenceUploadResponse, dependencies=[Depends(limit("upload"))])
async def upload_evidence(
    report_id: UUID = Form(...),
    access_token: str = Form(...),
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
) -> EvidenceUploadResponse:
    """Attach a photo / document / recording to an open reporting session.

    The old endpoint accepted anything with an ``access_token`` that merely started with ``tk_`` - anyone could fill the
    storage bucket. Now: real token check, size and type allowlist (from the file's bytes), per-report file cap.
    """
    report = await ReportEngine.authenticate(db, report_id, access_token)
    if report.case_id:
        raise AppError(409, "report_submitted", "This report has already been submitted. Evidence can no longer be added to it.")

    existing = (await db.execute(select(func.count()).select_from(Evidence).where(Evidence.report_id == report.id))).scalar_one()
    if existing >= settings.MAX_EVIDENCE_FILES_PER_REPORT:
        raise AppError(409, "too_many_files", f"A report can include at most {settings.MAX_EVIDENCE_FILES_PER_REPORT} files.")

    upload = await validate_upload(file)
    stored = await store_upload(upload, f"reports/{report.id}")
    evidence = Evidence(
        id=uuid.uuid4(),
        report_id=report.id,
        file_path=stored.ref,
        file_name=upload.display_name,
        mime_type=upload.detected.mime,
        size_bytes=len(upload.content),
        file_hash=upload.sha256,
        is_pii_cleansed=True,
    )
    db.add(evidence)
    try:
        await db.commit()
    except Exception:
        await db.rollback()
        await StorageService.delete(stored.ref)  # do not leave an orphaned file behind
        raise

    return EvidenceUploadResponse(
        evidence_id=evidence.id,
        file_name=upload.display_name,
        mime_type=upload.detected.mime,
        size_bytes=len(upload.content),
        hash=upload.sha256,
    )
