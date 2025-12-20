from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
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
    """
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

# Middleware: CORS
# HARDCODED FOR DEVELOPMENT - GUARANTEED TO WORK
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,  # MUST be False when using wildcard origins
    allow_methods=["*"],
    allow_headers=["*"],
)

# Exception Handlers
app.add_exception_handler(Exception, global_exception_handler)
app.add_exception_handler(StarletteHTTPException, http_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)

# Health Check
@app.get("/health", tags=["system"])
async def health_check():
    """
    Public health check endpoint for load balancers.
    """
    return {"status": "ok", "environment": settings.ENVIRONMENT}


from app.api.v1.public import reporting as public_reporting, evidence as public_evidence
from app.api.v1.admin import auth as admin_auth, reports as admin_reports, evidence as admin_evidence

app.include_router(public_reporting.router, prefix=f"{settings.API_V1_STR}/public/reports", tags=["reporting"])
app.include_router(public_evidence.router, prefix=f"{settings.API_V1_STR}/public/evidence", tags=["evidence"])
app.include_router(admin_auth.router, prefix=f"{settings.API_V1_STR}/admin/auth", tags=["admin-auth"])
app.include_router(admin_reports.router, prefix=f"{settings.API_V1_STR}/admin/reports", tags=["admin-reports"])
app.include_router(admin_evidence.router, prefix=f"{settings.API_V1_STR}/admin/evidence", tags=["admin-evidence"])
# app.include_router(api_router, prefix=settings.API_V1_STR)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
