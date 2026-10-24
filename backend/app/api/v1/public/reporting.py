"""Anonymous reporting session: create -> chat -> (submit)."""

from fastapi import APIRouter, BackgroundTasks, Body, Depends, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppError
from app.core.rate_limit import enforce, limit
from app.db.session import get_db
from app.schemas.report import CreateReportRequest, CredentialsResponse, MessageRequest, MessageResponse, ReportResponse, SessionAuthRequest
from app.services.report_engine import ReportEngine

router = APIRouter()


@router.post("/create", response_model=ReportResponse, dependencies=[Depends(limit("create_report"))])
async def create_report(
    _body: CreateReportRequest = Body(default_factory=CreateReportRequest), db: AsyncSession = Depends(get_db)
) -> ReportResponse:
    """Start an anonymous reporting session. Returns the session id and its (secret) access token."""
    report_id, token = await ReportEngine.create_session(db)
    return ReportResponse(report_id=report_id, access_token=token, message="Secure session established. Speak freely, I am listening.")


@router.post("/message", response_model=MessageResponse)
async def send_message(
    payload: MessageRequest,
    request: Request,
    background: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    """One chat turn. The reply is only returned (and stored) when it was actually produced - failures return an
    error status so the client can offer a retry instead of showing a fake assistant message."""
    enforce("send_message", request, extra_key=str(payload.report_id))
    report = await ReportEngine.authenticate(db, payload.report_id, payload.access_token)
    return await ReportEngine.process_message(db, report, payload.content, background)


@router.post("/credentials", response_model=CredentialsResponse)
async def pending_credentials(payload: SessionAuthRequest, request: Request, db: AsyncSession = Depends(get_db)) -> CredentialsResponse:
    """Re-fetch the Case ID / Secret Key of a just-submitted report if the original response was lost.

    Available only until the reporter acknowledges they saved them (or 24 h pass)."""
    enforce("send_message", request, extra_key=str(payload.report_id))
    report = await ReportEngine.authenticate(db, payload.report_id, payload.access_token)
    credentials = await ReportEngine.pending_credentials(db, report.id)
    if credentials is None:
        raise AppError(
            404, "credentials_not_available", "The credentials are no longer available. Use the Case ID and Secret Key you saved."
        )
    return credentials


@router.post("/credentials/ack", status_code=204)
async def acknowledge_credentials(payload: SessionAuthRequest, request: Request, db: AsyncSession = Depends(get_db)) -> Response:
    """The reporter confirms they saved their credentials; the server-side copy is deleted."""
    enforce("send_message", request, extra_key=str(payload.report_id))
    report = await ReportEngine.authenticate(db, payload.report_id, payload.access_token)
    await ReportEngine.acknowledge_credentials(db, report.id)
    return Response(status_code=204)
