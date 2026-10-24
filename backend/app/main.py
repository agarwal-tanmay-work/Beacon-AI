"""FastAPI application: wiring only - behaviour lives in ``app.services`` and ``app.api``."""

import asyncio
import contextlib
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.v1 import files as files_api
from app.api.v1.admin import auth as admin_auth
from app.api.v1.admin import reports as admin_reports
from app.api.v1.admin import system as admin_system
from app.api.v1.admin import updates as admin_updates
from app.api.v1.public import evidence as public_evidence
from app.api.v1.public import reporting as public_reporting
from app.api.v1.public import tracking as public_tracking
from app.core.config import settings
from app.core.exceptions import (
    AppError,
    app_error_handler,
    global_exception_handler,
    http_exception_handler,
    validation_exception_handler,
)
from app.core.logging import setup_logging
from app.core.middleware import BodySizeLimitMiddleware, SecurityHeadersMiddleware
from app.core.security import admin_login_configured
from app.db.init_db import ensure_schema
from app.db.session import dispose_engine
from app.services.gemini import gemini
from app.services.maintenance import maintenance_loop
from app.services.storage_service import StorageService

setup_logging()
logger = structlog.get_logger(__name__)


async def _initialise_database(app: FastAPI) -> None:
    """Create / upgrade the schema. Keeps retrying in the background if the database is unreachable,
    so the service can still bind its port (Render health checks) and heals itself when the DB comes back."""
    delay = 2.0
    while True:
        try:
            await ensure_schema()
            app.state.db_connected = True
            return
        except Exception as exc:  # noqa: BLE001 - any failure means "try again later"
            app.state.db_connected = False
            logger.error("db_init_failed", error_type=type(exc).__name__, retry_in=delay)
            await asyncio.sleep(delay)
            delay = min(delay * 2, 60.0)


def _log_configuration_warnings() -> None:
    if not admin_login_configured():
        logger.error("admin_login_disabled", hint="set ADMIN_PASSWORD_HASH (or ADMIN_PASSWORD) to enable the admin portal")
    if settings.weak_secret_key:
        logger.warning("weak_secret_key", hint="use at least 32 random characters")
    if not gemini.configured:
        logger.error("gemini_not_configured", hint="set GEMINI_API_KEY; the assistant will run in basic mode")
    if settings.is_production and settings.resolved_storage_backend == "local":
        logger.error("evidence_storage_is_ephemeral", hint="set SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY")
    if settings.is_production and settings.CORS_ORIGINS == [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3001",
    ]:
        logger.warning("cors_origins_default", hint="set CORS_ORIGINS to the admin portal's URL")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    app.state.db_connected = False
    _log_configuration_warnings()

    init_task = asyncio.create_task(_initialise_database(app))
    try:
        await asyncio.wait_for(asyncio.shield(init_task), timeout=25)  # normally done in well under a second
    except TimeoutError:
        logger.error("startup_degraded", message="database not ready yet - serving in degraded mode while retrying")

    background = [init_task, asyncio.create_task(maintenance_loop())]
    if gemini.configured:
        background.append(asyncio.create_task(gemini.discover_models()))
    logger.info(
        "startup", project=settings.PROJECT_NAME, environment=settings.ENVIRONMENT, storage=StorageService.backend(), ai=gemini.health()
    )

    yield

    for task in background:
        task.cancel()
    for task in background:
        with contextlib.suppress(asyncio.CancelledError, Exception):
            await task
    await gemini.aclose()
    await StorageService.aclose()
    await dispose_engine()
    logger.info("shutdown")


app = FastAPI(
    title=settings.PROJECT_NAME,
    version="6.0.0",
    description="Anonymous anti-corruption reporting platform",
    lifespan=lifespan,
    docs_url=f"{settings.API_V1_STR}/docs" if settings.docs_enabled else None,
    redoc_url=None,
    openapi_url=f"{settings.API_V1_STR}/openapi.json" if settings.docs_enabled else None,
)

# Middleware: the LAST one added is the OUTERMOST. Security headers wrap everything (including CORS pre-flights and
# 413 rejections), CORS wraps the size limit so browsers can read its error, the size limit sees the raw request.
app.add_middleware(
    BodySizeLimitMiddleware,
    default_limit=256 * 1024,
    upload_limit=settings.MAX_UPLOAD_BYTES + 512 * 1024,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=False,  # the admin portal sends a Bearer header, not cookies
    allow_methods=["GET", "POST", "PUT", "OPTIONS", "HEAD"],
    allow_headers=["Authorization", "Content-Type"],
    max_age=600,
)
app.add_middleware(SecurityHeadersMiddleware, docs_prefixes=(f"{settings.API_V1_STR}/docs", f"{settings.API_V1_STR}/openapi.json"))

app.add_exception_handler(AppError, app_error_handler)  # type: ignore[arg-type]
app.add_exception_handler(StarletteHTTPException, http_exception_handler)  # type: ignore[arg-type]
app.add_exception_handler(RequestValidationError, validation_exception_handler)  # type: ignore[arg-type]
app.add_exception_handler(Exception, global_exception_handler)


@app.get("/health", tags=["system"])
async def health(request: Request) -> dict[str, str]:
    """Liveness probe for Render / uptime monitors. Cheap: reads in-memory state only (no DB or AI round trip)."""
    return {
        "status": "ok",
        "environment": settings.ENVIRONMENT,
        "db": "connected" if getattr(request.app.state, "db_connected", False) else "disconnected",
        "ai": gemini.health(),
    }


@app.head("/health", include_in_schema=False)
async def health_head() -> Response:
    return Response(status_code=200)


api = settings.API_V1_STR
app.include_router(public_reporting.router, prefix=f"{api}/public/reports", tags=["reporting"])
app.include_router(public_evidence.router, prefix=f"{api}/public/evidence", tags=["evidence"])
app.include_router(public_tracking.router, prefix=f"{api}/public", tags=["tracking"])
app.include_router(files_api.router, prefix=api, tags=["files"])
app.include_router(admin_auth.router, prefix=f"{api}/admin/auth", tags=["admin-auth"])
app.include_router(admin_reports.router, prefix=f"{api}/admin/reports", tags=["admin-reports"])
app.include_router(admin_updates.router, prefix=f"{api}/admin/reports", tags=["admin-updates"])
app.include_router(admin_system.router, prefix=f"{api}/admin/system", tags=["admin-system"])
