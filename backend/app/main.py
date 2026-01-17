from contextlib import asynccontextmanager
from app.core.network_utils import force_ipv4_resolution

# Apply network patch immediately
force_ipv4_resolution()

from fastapi import FastAPI, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
import os
import traceback
import structlog

from app.core.config import settings
from app.core.logging import setup_logging
from app.core.exceptions import (
    global_exception_handler,
    http_exception_handler,
    validation_exception_handler,
)

# Setup Logging
setup_logging()
logger = structlog.get_logger()

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifecycle manager for the application.
    Initializes database (Local + Remote) on startup.
    """
    try:
        from app.db.init_db import run_init_db
        # Run DB initialization (includes network patch and connectivity check)
        await run_init_db()
        app.state.db_connected = True
    except Exception as e:
        logger.error("startup_failed", error=str(e))
        # FAIL SAFE: We must still bind the port so Render doesn't kill the service.
        # But we mark the app as unhealthy internally.
        print(f"[ERROR] DB Init Failed: {e}. Starting in degraded mode.", flush=True)
        app.state.db_connected = False
        # Do NOT raise e. Let uvicorn bind.
            
    logger.info("startup", project=settings.PROJECT_NAME)
    yield
    logger.info("shutdown")

app = FastAPI(
    title=settings.PROJECT_NAME,
    version="5.0.0",
    description="Government-grade Anti-Corruption Reporting System",
    lifespan=lifespan,
    docs_url=f"{settings.API_V1_STR}/docs",
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS if isinstance(settings.CORS_ORIGINS, list) else [settings.CORS_ORIGINS],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Custom Exception Handlers
app.add_exception_handler(Exception, global_exception_handler)
app.add_exception_handler(StarletteHTTPException, http_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)

# Health Check
@app.get("/health", tags=["system"])
async def health_check(request: Request):
    """
    Public health check endpoint.
    Returns 503 if DB is not connected (but port is open).
    """
    db_connected = getattr(app.state, "db_connected", False)
    if not db_connected:
        return JSONResponse(status_code=503, content={"status": "degraded", "environment": settings.ENVIRONMENT, "db": "disconnected"})
        
    return {"status": "ok", "environment": settings.ENVIRONMENT, "db": "connected"}


from app.api.v1.public import reporting as public_reporting, evidence as public_evidence, tracking as public_tracking
from app.api.v1.admin import auth as admin_auth, reports as admin_reports, evidence as admin_evidence, updates as admin_updates, files as admin_files

app.include_router(public_reporting.router, prefix=f"{settings.API_V1_STR}/public/reports", tags=["reporting"])
app.include_router(public_tracking.router, prefix=f"{settings.API_V1_STR}/public", tags=["tracking"]) # Mount at /public so it becomes /public/track
app.include_router(public_evidence.router, prefix=f"{settings.API_V1_STR}/public/evidence", tags=["evidence"])
app.include_router(admin_auth.router, prefix=f"{settings.API_V1_STR}/admin/auth", tags=["admin-auth"])
app.include_router(admin_reports.router, prefix=f"{settings.API_V1_STR}/admin/reports", tags=["admin-reports"])
app.include_router(admin_updates.router, prefix=f"{settings.API_V1_STR}/admin/reports", tags=["admin-updates"]) # Mount at /admin/reports for /{id}/update
app.include_router(admin_evidence.router, prefix=f"{settings.API_V1_STR}/admin/evidence", tags=["admin-evidence"])
app.include_router(admin_files.router, prefix=f"{settings.API_V1_STR}/admin/files", tags=["admin-files"])

# Mount Static Files (Uploads)
UPLOAD_DIR = "uploads"
if not os.path.exists(UPLOAD_DIR):
    os.makedirs(UPLOAD_DIR)
app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")
# app.include_router(api_router, prefix=settings.API_V1_STR)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000)
