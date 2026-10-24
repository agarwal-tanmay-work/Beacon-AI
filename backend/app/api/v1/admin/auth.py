"""Administrator sign-in."""

import asyncio

import structlog
from fastapi import APIRouter, Request

from app.core.config import settings
from app.core.exceptions import AppError
from app.core.rate_limit import client_ip, login_failures, raise_if_blocked
from app.core.security import admin_login_configured, admin_subject, create_access_token, verify_admin_credentials
from app.schemas.report import LoginRequest

router = APIRouter()
logger = structlog.get_logger(__name__)


@router.post("/login")
async def login(payload: LoginRequest, request: Request) -> dict:
    """Exchange the admin username + password for a short-lived JWT.

    Fails closed: there is no built-in default password. The old code accepted the literal password
    ``BeaconAI@26`` (visible in the public repository) whenever ``ADMIN_PASSWORD_HASH`` was not set.
    """
    if not admin_login_configured():
        logger.error("admin_login_not_configured")
        raise AppError(
            503,
            "admin_login_not_configured",
            "Admin sign-in is not configured on this server. Set ADMIN_PASSWORD_HASH (or ADMIN_PASSWORD).",
        )

    ip = client_ip(request)
    if settings.RATE_LIMIT_ENABLED:
        raise_if_blocked(login_failures.blocked_for(ip), message="Too many failed sign-in attempts. Please wait 15 minutes and try again.")

    if not await asyncio.to_thread(verify_admin_credentials, payload.username, payload.password):
        login_failures.record_failure(ip)
        logger.warning("admin_login_failed")
        await asyncio.sleep(0.5)  # blunts online guessing a little more
        raise AppError(401, "invalid_credentials", "Invalid credentials.")

    login_failures.reset(ip)
    logger.info("admin_login_succeeded")
    return {
        "access_token": create_access_token(admin_subject()),
        "token_type": "bearer",
        "user": {"username": admin_subject(), "role": "admin"},
    }
