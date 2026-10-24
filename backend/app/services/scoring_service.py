"""Background analysis of a submitted case: evidence analysis -> AI summary -> credibility score.

Reliability model (replacing "retry inline for up to 7 minutes, then give up forever"):

* every step is individually retried by the Gemini client (model fallback chain);
* progress is saved step by step - a scoring failure no longer throws away a finished summary;
* a failed or interrupted analysis is marked ``failed`` / left ``processing`` and picked up again by the
  maintenance sweep (``app.services.maintenance``) with back-off, so a Render restart, a quota outage or a
  retired model can no longer leave a case on "Pending analysis" forever.
"""

import asyncio
from typing import Any
from uuid import UUID

import structlog
from sqlalchemy import select

from app.core.time_utils import utc_now
from app.db.session import open_session
from app.models.beacon import Beacon
from app.models.report import Evidence, ReportConversation, SenderType
from app.schemas.ai import EvidenceDigest
from app.services import ai_service
from app.services.evidence_processor import EvidenceProcessor
from app.services.gemini import GeminiError
from app.services.scoring_rules import finalize_score

logger = structlog.get_logger(__name__)

DISCLAIMER = "This analysis reflects the information provided. It does not verify the authenticity, truth or legality of any claim."
_FINAL_MESSAGE_PREFIX = "Thank you for your courage in reporting this."

_in_flight: set[str] = set()
_lock: asyncio.Lock | None = None
_lock_loop: asyncio.AbstractEventLoop | None = None


def _global_lock() -> asyncio.Lock:
    """Only one analysis at a time: keeps Gemini usage predictable. (Re-created if the event loop changed.)"""
    global _lock, _lock_loop
    loop = asyncio.get_running_loop()
    if _lock is None or _lock_loop is not loop:
        _lock, _lock_loop = asyncio.Lock(), loop
    return _lock


def evidence_summary(evidence: Evidence, analysis: dict[str, Any] | None) -> dict[str, Any]:
    """The admin-facing record of one uploaded file (storage ref + what the analysis found)."""
    entry: dict[str, Any] = {
        "file_name": evidence.file_name,
        "mime_type": evidence.mime_type,
        "size_bytes": evidence.size_bytes,
        "file_path": evidence.file_path,
        "analyzed": bool(analysis and analysis.get("analysis_available")),
    }
    if analysis:
        entry["kind"] = analysis.get("kind")
        entry["summary"] = (analysis.get("description") or analysis.get("transcript") or analysis.get("extracted_text") or "")[:400]
        entry["quality_notes"] = analysis.get("quality_notes") or []
    return entry


class ScoringService:
    @classmethod
    def is_running(cls, case_id: str) -> bool:
        return case_id in _in_flight

    @classmethod
    async def run_background_scoring(cls, report_id: str, case_id: str) -> None:
        """Entry point used by BackgroundTasks, the admin 're-analyse' button and the maintenance sweep."""
        if case_id in _in_flight:
            return
        _in_flight.add(case_id)
        try:
            async with _global_lock():
                await cls._run(UUID(report_id), case_id)
        except Exception:  # noqa: BLE001 - a background task must never crash the worker
            logger.exception("background_scoring_crashed", case_id=case_id)
        finally:
            _in_flight.discard(case_id)

    @classmethod
    async def _run(cls, report_id: UUID, case_id: str) -> None:
        async with open_session() as db:
            beacon = (await db.execute(select(Beacon).where(Beacon.case_id == case_id))).scalar_one_or_none()
            if beacon is None:
                logger.error("analysis_case_not_found", case_id=case_id)
                return

            beacon.analysis_status = "processing"
            beacon.analysis_attempts = (beacon.analysis_attempts or 0) + 1
            await db.commit()
            logger.info("analysis_started", case_id=case_id, attempt=beacon.analysis_attempts)

            try:
                lines = [
                    ("user" if sender == SenderType.USER else "assistant", text)
                    for sender, text in (
                        await db.execute(
                            select(ReportConversation.sender, ReportConversation.content_redacted)
                            .where(ReportConversation.report_id == report_id)
                            .order_by(ReportConversation.created_at, ReportConversation.id)
                        )
                    ).all()
                    if not text.startswith(_FINAL_MESSAGE_PREFIX)
                ]
                evidence_rows = list(
                    (await db.execute(select(Evidence).where(Evidence.report_id == report_id).order_by(Evidence.uploaded_at))).scalars()
                )

                # 1. evidence - failures degrade the digest, they do not abort the analysis
                digests: list[EvidenceDigest] = []
                analyses: list[dict[str, Any]] = []
                seen_hashes: set[str] = set()
                for evidence in evidence_rows:
                    try:
                        analysis = await EvidenceProcessor.analyze(evidence)
                    except Exception as exc:  # noqa: BLE001
                        logger.warning("evidence_analysis_failed", case_id=case_id, error_type=type(exc).__name__)
                        analysis = {"kind": "unknown", "analysis_available": False}
                    duplicate = evidence.file_hash in seen_hashes
                    seen_hashes.add(evidence.file_hash)
                    analyses.append(analysis)
                    digests.append(EvidenceProcessor.to_digest(evidence, analysis, duplicate=duplicate))
                beacon.evidence_files = [evidence_summary(e, a) for e, a in zip(evidence_rows, analyses, strict=True)]
                await db.commit()

                # 2. summary (kept even if scoring fails below)
                if not beacon.ai_summary:
                    beacon.ai_summary = await ai_service.summarize_report(lines, digests)
                    await db.commit()

                # 3. score
                final = finalize_score(await ai_service.score_report(lines, digests), digests)
                beacon.credibility_score = final.total
                beacon.ai_explanation = {
                    "rationale": final.rationale,
                    "confidence": final.confidence,
                    "limitations": final.limitations,
                    "safety": DISCLAIMER,
                    "narrative_score": final.narrative,
                    "evidence_score": final.evidence,
                    "behavioral_score": final.behavioral,
                }
                beacon.score_explanation = " ".join(
                    [f"This report received a {final.confidence} confidence rating.", *final.rationale, *final.limitations]
                )
                beacon.analysis_status = "completed"
                beacon.analysis_last_error = None
                await db.commit()
                logger.info("analysis_completed", case_id=case_id, score=final.total, confidence=final.confidence)

            except GeminiError as exc:
                await cls._mark_failed(db, case_id, f"{exc.kind}: {str(exc)[:200]}")
            except Exception as exc:  # noqa: BLE001
                logger.exception("analysis_failed_unexpectedly", case_id=case_id)
                await cls._mark_failed(db, case_id, f"{type(exc).__name__}")

    @classmethod
    async def _mark_failed(cls, db: Any, case_id: str, reason: str) -> None:
        await db.rollback()
        beacon = (await db.execute(select(Beacon).where(Beacon.case_id == case_id))).scalar_one()
        beacon.analysis_status = "failed"
        beacon.analysis_last_error = f"{utc_now().isoformat()} {reason}"
        await db.commit()
        logger.warning("analysis_failed", case_id=case_id, reason=reason, attempts=beacon.analysis_attempts)
