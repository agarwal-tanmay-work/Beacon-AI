"""Periodic housekeeping, run once after start-up and then on a timer.

* **Recover analyses** that never finished (process restarted mid-job, AI outage, retired model ...).
* **Scrub legacy plaintext secret keys**: earlier versions stored every case's Secret Key in clear text next to
  its hash. The hash is verified against the plaintext first, then the plaintext is removed.
* **Expire uncollected credentials**: the escrow copy a reporter can re-fetch after a lost response is deleted
  after 24 h (or immediately when they acknowledge it).
"""

import asyncio
from datetime import timedelta

import structlog
from sqlalchemy import select

from app.core.config import settings
from app.core.security import hash_secret, normalize_case_secret, verify_secret
from app.core.time_utils import parse_iso_utc, utc_now
from app.db.session import open_session
from app.models.beacon import Beacon
from app.models.report import Report, ReportStateTracking
from app.services.gemini import gemini
from app.services.report_engine import CREDENTIAL_ESCROW
from app.services.scoring_service import ScoringService

logger = structlog.get_logger(__name__)

PENDING_GRACE = timedelta(minutes=3)  # a fresh 'pending' case still has its own background task queued
PROCESSING_STALE = timedelta(minutes=20)
MAX_RECOVERIES_PER_RUN = 5


def retry_delay(attempts: int) -> timedelta:
    """Back-off between failed analysis attempts: 4, 8, 16 ... capped at 1 hour."""
    return timedelta(minutes=min(2 ** (attempts + 1), 60))


async def recover_stalled_analyses() -> int:
    now = utc_now()
    async with open_session() as db:
        rows = (
            await db.execute(
                select(Beacon.case_id, Beacon.analysis_status, Beacon.analysis_attempts, Beacon.updated_at)
                .where(Beacon.analysis_status != "completed", Beacon.analysis_attempts < settings.ANALYSIS_MAX_ATTEMPTS)
                .order_by(Beacon.updated_at)
                .limit(50)
            )
        ).all()
        due: list[str] = []
        for case_id, status, attempts, updated in rows:
            updated = updated if updated.tzinfo else updated.replace(tzinfo=now.tzinfo)
            age = now - updated
            if (
                (status == "pending" and age > PENDING_GRACE)
                or (status == "processing" and age > PROCESSING_STALE)
                or (status == "failed" and age > retry_delay(attempts or 0))
            ) and not ScoringService.is_running(case_id):
                due.append(case_id)
        due = due[:MAX_RECOVERIES_PER_RUN]
        reports = (
            {
                case_id: str(report_id)
                for case_id, report_id in (await db.execute(select(Report.case_id, Report.id).where(Report.case_id.in_(due)))).all()
            }
            if due
            else {}
        )

    for case_id in due:
        report_id = reports.get(case_id)
        if report_id is None:
            logger.warning("analysis_recovery_no_session", case_id=case_id)
            continue
        logger.info("analysis_recovery", case_id=case_id)
        await ScoringService.run_background_scoring(report_id, case_id)
    return len(due)


async def scrub_plaintext_secret_keys(batch: int = 100) -> int:
    scrubbed = 0
    async with open_session() as db:
        for beacon in (await db.execute(select(Beacon).where(Beacon.secret_key.is_not(None)).limit(batch))).scalars():
            plain = beacon.secret_key or ""
            hash_matches = bool(beacon.secret_key_hash) and await asyncio.to_thread(verify_secret, plain, beacon.secret_key_hash)
            if not hash_matches:
                # No (matching) hash: derive one from the plaintext so the reporter keeps access, then drop the plaintext.
                beacon.secret_key_hash = await asyncio.to_thread(hash_secret, normalize_case_secret(plain))
            beacon.secret_key = None
            scrubbed += 1
        await db.commit()
    if scrubbed:
        logger.info("plaintext_secret_keys_scrubbed", count=scrubbed)
    return scrubbed


async def purge_expired_credentials() -> int:
    cutoff = utc_now() - CREDENTIAL_ESCROW
    purged = 0
    async with open_session() as db:
        states = (
            await db.execute(
                select(ReportStateTracking)
                .join(Report, Report.id == ReportStateTracking.report_id)
                .where(Report.case_id.is_not(None), Report.created_at > utc_now() - timedelta(days=7))
            )
        ).scalars()
        for state in states:
            creds = (state.context_data or {}).get("credentials")
            if creds and parse_iso_utc(creds.get("issued_at", "1970-01-01T00:00:00+00:00")) < cutoff:
                data = dict(state.context_data)
                data.pop("credentials")
                state.context_data = data
                purged += 1
        await db.commit()
    return purged


async def run_maintenance_once() -> None:
    for name, job in (
        ("scrub_secret_keys", scrub_plaintext_secret_keys),
        ("purge_credentials", purge_expired_credentials),
        ("recover_analyses", recover_stalled_analyses),
    ):
        try:
            await job()
        except Exception:  # noqa: BLE001 - one failing job must not stop the others (or the loop)
            logger.exception("maintenance_job_failed", job=name)
    gemini.schedule_discovery_if_stale()


async def maintenance_loop(initial_delay: float = 20.0) -> None:
    await asyncio.sleep(initial_delay)
    while True:
        await run_maintenance_once()
        await asyncio.sleep(settings.ANALYSIS_SWEEP_INTERVAL_SECONDS)
