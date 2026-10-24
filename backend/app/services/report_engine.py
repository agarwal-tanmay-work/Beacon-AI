"""One reporting session from first message to submitted case.

Request flow for ``process_message`` (and why it is shaped this way):

1. **Authenticate** the session token against its stored hash (the old code only checked the ``tk_`` prefix).
2. **Read** history / facts / evidence, then *commit* - this releases the database connection before the slow
   AI call instead of holding a pooled connection "idle in transaction" for up to 35 s.
3. **Think**: analyse any newly uploaded files, then run the chat agent (AI with fallback chain, or basic mode).
4. **Write** the user message, the assistant reply and the updated facts in ONE transaction. If anything fails
   before this point nothing was stored, so the user can simply resend (no orphaned half-turns, no
   "trouble connecting to my brain" apology persisted as if the assistant had said it).
5. **Submit** only when the server's own checks pass (required facts present) - never because of what a model wrote.
"""

import asyncio
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from typing import Any
from uuid import UUID

import structlog
from fastapi import BackgroundTasks
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import AppError
from app.core.security import generate_access_token, generate_case_secret, hash_access_token, hash_secret, verify_access_token
from app.core.time_utils import parse_iso_utc, utc_now
from app.models.beacon import Beacon
from app.models.report import Evidence, Report, ReportConversation, ReportStateTracking, ReportStatus, SenderType
from app.schemas.ai import FACT_FIELDS, SKIPPED
from app.schemas.report import CredentialsResponse, MessageResponse
from app.services import chat_agent
from app.services.case_service import CaseService
from app.services.chat_agent import clean_facts, is_real, missing_basics
from app.services.evidence_processor import EvidenceProcessor
from app.services.gemini import GeminiBlocked

logger = structlog.get_logger(__name__)

CREDENTIAL_ESCROW = timedelta(hours=24)

FINAL_MESSAGE = (
    "Thank you for your courage in reporting this.\n"
    "Your Case ID is: {case_id}\n"
    "Your Secret Key is: {secret_key}\n\n"
    "**IMPORTANT**: Please save both of these safely to track your case status. "
    "We will investigate and take appropriate action. You've done the right thing by speaking up."
)
# What is written into the stored transcript - the secret key is deliberately not part of it.
STORED_FINAL_MESSAGE = "Thank you for your courage in reporting this. Your report was submitted as Case ID {case_id}."
ALREADY_SUBMITTED = (
    "Your report has already been submitted as Case ID {case_id}. For your security the Secret Key is shown only once, "
    "at submission. Use your Case ID and Secret Key on the Track page to follow up."
)

_session_locks: dict[UUID, asyncio.Lock] = {}


@asynccontextmanager
async def _exclusive(report_id: UUID):
    """One message at a time per report (a double-click or a retry must not run two AI turns in parallel)."""
    lock = _session_locks.setdefault(report_id, asyncio.Lock())
    if lock.locked():
        raise AppError(409, "busy", "I'm still working on your previous message. Please wait a moment.", retry_after=3)
    async with lock:
        try:
            yield
        finally:
            _session_locks.pop(report_id, None)


def build_incident_summary(facts: dict[str, str]) -> str:
    """Neutral paragraph from the structured facts - shown until the AI summary is ready."""
    parts = []
    if is_real(facts.get("what")):
        parts.append(facts["what"].rstrip(". ") + ".")
    for label, key in (("Location", "where"), ("Date/time", "when"), ("Individuals involved", "who")):
        if is_real(facts.get(key)):
            parts.append(f"{label}: {facts[key].rstrip('. ')}.")
    return " ".join(parts) or "Report submitted."


def _evidence_entry(evidence: Evidence) -> dict[str, Any]:
    return {
        "file_name": evidence.file_name,
        "mime_type": evidence.mime_type,
        "size_bytes": evidence.size_bytes,
        "file_path": evidence.file_path,
    }


class ReportEngine:
    # ---- sessions --------------------------------------------------------------------
    @classmethod
    async def create_session(cls, db: AsyncSession) -> tuple[UUID, str]:
        token = generate_access_token()
        report = Report(id=uuid.uuid4(), access_token_hash=hash_access_token(token), status=ReportStatus.NEW)
        db.add_all(
            [
                report,
                ReportStateTracking(
                    report_id=report.id,
                    current_step="ACTIVE",
                    context_data={"initialized_at": utc_now().isoformat(), "extracted": {}},
                ),
            ]
        )
        await db.commit()
        return report.id, token

    @classmethod
    async def authenticate(cls, db: AsyncSession, report_id: UUID, token: str) -> Report:
        report = await db.get(Report, report_id)
        if report is None or not verify_access_token(token, report.access_token_hash):
            raise AppError(401, "invalid_session", "This reporting session is not valid or has expired. Please start a new report.")
        return report

    # ---- credentials (held only until the reporter confirms they saved them) ---------
    @classmethod
    async def _state(cls, db: AsyncSession, report_id: UUID) -> ReportStateTracking:
        state = await db.get(ReportStateTracking, report_id)
        if state is None:  # sessions created by very old versions
            state = ReportStateTracking(report_id=report_id, current_step="ACTIVE", context_data={"extracted": {}})
            db.add(state)
            await db.flush()
        return state

    @classmethod
    async def pending_credentials(cls, db: AsyncSession, report_id: UUID) -> CredentialsResponse | None:
        state = await db.get(ReportStateTracking, report_id)
        creds = (state.context_data or {}).get("credentials") if state else None
        if not creds:
            return None
        issued = creds.get("issued_at")
        if issued and utc_now() - parse_iso_utc(issued) > CREDENTIAL_ESCROW:
            await cls.acknowledge_credentials(db, report_id)  # expired: drop the plaintext key
            return None
        return CredentialsResponse(case_id=creds["case_id"], secret_key=creds["secret_key"])

    @classmethod
    async def acknowledge_credentials(cls, db: AsyncSession, report_id: UUID) -> None:
        state = await db.get(ReportStateTracking, report_id)
        if state and "credentials" in (state.context_data or {}):
            data = dict(state.context_data)
            data.pop("credentials", None)
            state.context_data = data
            await db.commit()

    # ---- the conversation --------------------------------------------------------------
    @classmethod
    async def process_message(cls, db: AsyncSession, report: Report, content: str, background: BackgroundTasks) -> MessageResponse:
        rid, existing_case = report.id, report.case_id
        if existing_case:
            return await cls._already_submitted(db, rid, existing_case)
        async with _exclusive(rid):
            return await cls._process_message(db, rid, content, background)

    @classmethod
    async def _process_message(cls, db: AsyncSession, rid: UUID, content: str, background: BackgroundTasks) -> MessageResponse:
        # ---- 2. read -----------------------------------------------------------------
        state = await cls._state(db, rid)
        ctx: dict[str, Any] = dict(state.context_data or {})
        facts = clean_facts(ctx.get("extracted"))
        pending_field = ctx.get("pending_field")
        rows = (
            await db.execute(
                select(ReportConversation.sender, ReportConversation.content_redacted)
                .where(ReportConversation.report_id == rid)
                .order_by(ReportConversation.created_at, ReportConversation.id)
            )
        ).all()
        history = [("user" if sender == SenderType.USER else "assistant", text) for sender, text in rows]
        if len(history) >= settings.MAX_MESSAGES_PER_REPORT:
            raise AppError(
                409,
                "conversation_too_long",
                "This conversation has become very long. Please say 'I'm done' to submit your report with what we have.",
            )
        evidence_rows = list((await db.execute(select(Evidence).where(Evidence.report_id == rid).order_by(Evidence.uploaded_at))).scalars())
        await db.commit()  # release the connection before the slow part

        # ---- 3. think ----------------------------------------------------------------
        notes = dict(ctx.get("evidence_notes") or {})
        fresh = [e for e in evidence_rows if str(e.id) not in notes]
        if fresh:
            analyses = await asyncio.gather(*(EvidenceProcessor.analyze(e, quick=True) for e in fresh), return_exceptions=True)
            for evidence, analysis in zip(fresh, analyses, strict=True):
                if isinstance(analysis, BaseException):
                    logger.warning("evidence_note_failed", error_type=type(analysis).__name__)
                    notes[str(evidence.id)] = f"File '{evidence.file_name}': uploaded"
                else:
                    notes[str(evidence.id)] = EvidenceProcessor.chat_note(evidence, analysis)
        evidence_note = "\n".join(notes[str(e.id)] for e in fresh) or None
        if evidence_rows and not is_real(facts.get("evidence")):
            facts["evidence"] = f"Uploaded ({len(evidence_rows)} file{'s' if len(evidence_rows) != 1 else ''})"

        try:
            turn = await chat_agent.respond(
                [*history, ("user", content)],
                facts,
                pending_field=pending_field,
                evidence_count=len(evidence_rows),
                evidence_note=evidence_note,
            )
        except GeminiBlocked as exc:
            await db.rollback()
            logger.info("chat_message_blocked", reason=exc.reason)
            raise AppError(422, "message_blocked", "I couldn't process that message automatically. Could you try rephrasing it?") from exc

        # ---- the server decides about submission --------------------------------------
        reply, asked, merged = turn.reply, turn.asked_about, turn.facts
        if evidence_rows and not is_real(merged.get("evidence")):
            merged["evidence"] = facts["evidence"]
        submit = False
        if turn.ready_to_submit:
            missing = missing_basics(merged)
            if missing:
                asked = missing[0]
                reply = "Before I can submit your report I still need one detail. " + chat_agent.question_for(missing[0])
                logger.info("submission_deferred_missing_facts", missing=missing)
            else:
                submit = True

        # ---- 4. write ------------------------------------------------------------------
        now = utc_now()
        db.add(ReportConversation(report_id=rid, sender=SenderType.USER, content_redacted=content, created_at=now))
        ctx.update(extracted=merged, pending_field=None if asked in ("none", None) else asked, mode=turn.mode, evidence_notes=notes)

        if not submit:
            db.add(
                ReportConversation(
                    report_id=rid, sender=SenderType.SYSTEM, content_redacted=reply, created_at=now + timedelta(milliseconds=1)
                )
            )
            state.context_data = ctx
            await db.commit()
            return MessageResponse(
                report_id=rid,
                sender=SenderType.SYSTEM,
                content=reply,
                timestamp=utc_now(),
                next_step="ACTIVE",
                mode=turn.mode,
                notice=turn.notice,
            )

        return await cls._submit(db, rid, state, ctx, merged, evidence_rows, turn.mode, background, now)

    # ---- submission -----------------------------------------------------------------------
    @classmethod
    async def _submit(
        cls,
        db: AsyncSession,
        rid: UUID,
        state: ReportStateTracking,
        ctx: dict[str, Any],
        facts: dict[str, str],
        evidence_rows: list[Evidence],
        mode: str,
        background: BackgroundTasks,
        now: datetime,
    ) -> MessageResponse:
        # Serialise with any other request finishing this same report (cross-process safe on PostgreSQL).
        locked = (
            await db.execute(select(Report).where(Report.id == rid).with_for_update().execution_options(populate_existing=True))
        ).scalar_one()
        if locked.case_id:
            winner = locked.case_id
            await db.rollback()  # (ORM instances are expired by this - only plain values are used from here on)
            return await cls._already_submitted(db, rid, winner)

        case_id = await CaseService.next_case_id(db)  # on PostgreSQL this holds an advisory lock until the commit below
        secret = generate_case_secret()
        secret_hash = await asyncio.to_thread(hash_secret, secret)

        db.add(
            Beacon(
                case_id=case_id,
                reported_at=now,
                incident_summary=build_incident_summary(facts),
                reporter_details={f: facts[f] for f in FACT_FIELDS if facts.get(f) and facts[f] != SKIPPED},
                secret_key_hash=secret_hash,
                status="Received",
                evidence_files=[_evidence_entry(e) for e in evidence_rows],
                analysis_status="pending",
            )
        )
        locked.case_id = case_id
        for evidence in evidence_rows:
            evidence.case_id = case_id
        db.add(
            ReportConversation(
                report_id=rid,
                sender=SenderType.SYSTEM,
                content_redacted=STORED_FINAL_MESSAGE.format(case_id=case_id),
                created_at=now + timedelta(milliseconds=1),
            )
        )
        ctx["credentials"] = {"case_id": case_id, "secret_key": secret, "issued_at": now.isoformat()}
        ctx["pending_field"] = None
        state.context_data = ctx
        await db.commit()

        logger.info("report_submitted", case_id=case_id, evidence_files=len(evidence_rows), mode=mode)
        from app.services.scoring_service import ScoringService  # local import avoids a module cycle

        background.add_task(ScoringService.run_background_scoring, str(rid), case_id)
        return MessageResponse(
            report_id=rid,
            sender=SenderType.SYSTEM,
            content=FINAL_MESSAGE.format(case_id=case_id, secret_key=secret),
            timestamp=utc_now(),
            next_step="COMPLETED",
            case_id=case_id,
            secret_key=secret,
            mode="ai" if mode == "ai" else "basic",
        )

    @classmethod
    async def _already_submitted(cls, db: AsyncSession, rid: UUID, case_id: str) -> MessageResponse:
        """Replay for a session that already produced a case (retry, second tab, lost response)."""
        creds = await cls.pending_credentials(db, rid)
        if creds:
            return MessageResponse(
                report_id=rid,
                sender=SenderType.SYSTEM,
                content=FINAL_MESSAGE.format(case_id=creds.case_id, secret_key=creds.secret_key),
                timestamp=utc_now(),
                next_step="COMPLETED",
                case_id=creds.case_id,
                secret_key=creds.secret_key,
            )
        return MessageResponse(
            report_id=rid,
            sender=SenderType.SYSTEM,
            content=ALREADY_SUBMITTED.format(case_id=case_id),
            timestamp=utc_now(),
            next_step="COMPLETED",
            case_id=case_id,
        )
