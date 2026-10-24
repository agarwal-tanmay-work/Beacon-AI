"""Operational status for administrators (never contains secrets)."""

from fastapi import APIRouter, Depends, Request
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_admin
from app.core.config import settings
from app.db.session import get_db
from app.models.beacon import Beacon
from app.services.gemini import gemini
from app.services.storage_service import StorageService

router = APIRouter(dependencies=[Depends(get_current_admin)])


@router.get("/status")
async def system_status(request: Request, db: AsyncSession = Depends(get_db)) -> dict:
    """AI model chain health, storage backend, and any configuration warnings - for the admin to check at a glance."""
    counts = dict((await db.execute(select(Beacon.analysis_status, func.count()).group_by(Beacon.analysis_status))).all())
    warnings: list[str] = []
    ai = gemini.status()
    if ai["state"] == "unconfigured":
        warnings.append("GEMINI_API_KEY is not set - the assistant runs in basic mode and cases are not scored.")
    elif ai["state"] == "key_invalid":
        warnings.append(
            f"Google rejected the Gemini API key ({ai['key_error']}). Create a new key in Google AI Studio and update GEMINI_API_KEY."
        )
    elif ai["state"] == "degraded":
        warnings.append("Every configured Gemini model is currently unavailable. The assistant is using basic mode.")
    if settings.weak_secret_key:
        warnings.append("SECRET_KEY is shorter than 32 characters.")
    if StorageService.backend() == "local" and settings.is_production:
        warnings.append("Evidence is stored on the local disk, which is erased on every Render deploy. Configure Supabase storage.")
    return {
        "environment": settings.ENVIRONMENT,
        "database": "connected" if getattr(request.app.state, "db_connected", False) else "disconnected",
        "storage": StorageService.backend(),
        "ai": ai,
        "analysis_queue": counts,
        "warnings": warnings,
    }
