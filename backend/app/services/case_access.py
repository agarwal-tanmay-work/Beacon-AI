"""Authenticating a reporter who comes back with a Case ID + Secret Key."""

import asyncio

import structlog
from fastapi import Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import AppError
from app.core.rate_limit import client_ip, raise_if_blocked, track_case_failures, track_ip_failures
from app.core.security import (
    burn_verification_time,
    constant_time_equals,
    hash_secret,
    normalize_case_id,
    normalize_case_secret,
    verify_secret,
)
from app.models.beacon import Beacon

logger = structlog.get_logger(__name__)


def _invalid() -> AppError:
    return AppError(401, "invalid_credentials", "Invalid Case ID or Secret Key.")


async def authenticate_case(db: AsyncSession, request: Request, raw_case_id: str, raw_secret: str) -> Beacon:
    """Return the case if both values are right, otherwise raise one uniform 401.

    Protections: failed-attempt lockouts per client IP and per case ID (brute force), identical error and
    comparable CPU cost whether the case exists or not (no enumeration), constant-time comparison, tolerant
    input (case, spaces, dashes) so honest typos of formatting do not count against the reporter.
    """
    case_id = normalize_case_id(raw_case_id)
    secret = normalize_case_secret(raw_secret)
    ip = client_ip(request)

    if settings.RATE_LIMIT_ENABLED:
        raise_if_blocked(max(track_ip_failures.blocked_for(ip), track_case_failures.blocked_for(case_id)))

    case = (await db.execute(select(Beacon).where(Beacon.case_id == case_id))).scalar_one_or_none()

    verified = False
    if case is not None and case.secret_key_hash:
        verified = await asyncio.to_thread(verify_secret, secret, case.secret_key_hash)
    elif case is not None and case.secret_key:  # legacy row that has not been through the maintenance scrub yet
        verified = constant_time_equals(normalize_case_secret(case.secret_key), secret)
        if verified:
            case.secret_key_hash = await asyncio.to_thread(hash_secret, secret)
            case.secret_key = None
            await db.commit()
    else:
        await asyncio.to_thread(burn_verification_time)

    if not verified:
        if settings.RATE_LIMIT_ENABLED:
            track_ip_failures.record_failure(ip)
            track_case_failures.record_failure(case_id)
        logger.info("case_authentication_failed")
        raise _invalid()
    assert case is not None
    return case
