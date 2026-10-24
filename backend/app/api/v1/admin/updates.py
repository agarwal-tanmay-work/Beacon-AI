"""Public status updates: the investigator writes a note, an AI rewrites it for the reporter."""

from uuid import UUID

import structlog
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_admin
from app.api.v1.admin.reports import get_case
from app.core.exceptions import AppError
from app.core.time_utils import utc_now
from app.db.session import get_db
from app.models.beacon_update import BeaconUpdate
from app.schemas.report import AdminUpdateRequest, AdminUpdateResponse
from app.services import ai_service
from app.services.gemini import GeminiBlocked, GeminiError

router = APIRouter(dependencies=[Depends(get_current_admin)])
logger = structlog.get_logger(__name__)


@router.post("/{case_uuid}/update", response_model=AdminUpdateResponse)
async def publish_update(case_uuid: UUID, payload: AdminUpdateRequest, db: AsyncSession = Depends(get_db)) -> AdminUpdateResponse:
    case = await get_case(db, case_uuid)

    rewritten = True
    if payload.publish_raw:
        public_text, rewritten = payload.raw_update, False
    else:
        try:
            public_text = await ai_service.rewrite_update(payload.raw_update)
        except (GeminiBlocked, GeminiError) as exc:
            # Never fall back to publishing the internal note unasked - it may contain details meant for investigators only.
            logger.warning("update_rewrite_unavailable", reason=exc.kind)
            raise AppError(
                503,
                "ai_unavailable",
                "The AI rewrite is unavailable right now. Try again in a moment, or choose 'publish as written'.",
                retry_after=getattr(exc, "retry_after", None) or 15,
            ) from exc

    now = utc_now()
    db.add(BeaconUpdate(case_id=case.case_id, raw_update=payload.raw_update, public_update=public_text, updated_by=payload.updated_by))
    case.last_raw_status = payload.raw_update
    case.last_framed_status = public_text
    case.last_updated_at = now
    if payload.status:
        case.status = payload.status
    await db.commit()
    return AdminUpdateResponse(
        status="Pending" if case.status == "Received" else case.status, public_update=public_text, timestamp=now, rewritten=rewritten
    )
