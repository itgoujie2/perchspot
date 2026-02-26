"""
FastAPI application entry point
"""
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from contextlib import asynccontextmanager
import time
import logging

from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from app.config import settings
from app.database.connection import init_db
from app.api.v1 import router as api_v1_router

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Rate limiter
limiter = Limiter(key_func=get_remote_address)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add security headers to all responses"""

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)

        # Security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        # HSTS - only in production (when not DEBUG)
        if not settings.DEBUG:
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains; preload"

        return response


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan context manager for startup and shutdown events
    """
    # Startup
    logger.info("Starting Perchspot API...")

    # Initialize database
    try:
        init_db()
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        raise

    # Pre-load knowledge files into memory (~170KB, instant)
    try:
        from app.services.knowledge.skill_knowledge_service import preload_all_files
        loaded = preload_all_files()
        logger.info(f"Knowledge files pre-loaded: {loaded} files")
    except Exception as e:
        logger.warning(f"Failed to pre-load knowledge files: {e}")

    # Clean up stuck in_progress analysis jobs from previous crash/restart
    try:
        from sqlalchemy import text
        from app.database.connection import engine
        with engine.connect() as conn:
            result = conn.execute(
                text(
                    "UPDATE analysis_jobs "
                    "SET status = 'failed', error_message = 'server_restart', "
                    "    completed_at = NOW() "
                    "WHERE status = 'in_progress'"
                )
            )
            conn.commit()
            if result.rowcount > 0:
                logger.warning(f"Marked {result.rowcount} stuck in_progress jobs as failed (server_restart)")
    except Exception as e:
        logger.warning(f"Failed to clean up stuck jobs: {e}")

    yield

    # Shutdown
    logger.info("Shutting down Perchspot API...")


# Create FastAPI application
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Perchspot - AI-powered property analysis",
    lifespan=lifespan,
    # Disable docs in production for security
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
)

# Add rate limiter state
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Add security headers middleware
app.add_middleware(SecurityHeadersMiddleware)


# CORS Middleware - specific methods and headers for security
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Requested-With", "X-Admin-Password"],
    expose_headers=["X-Process-Time"],
    max_age=600,  # Cache preflight for 10 minutes
)


# Request timing middleware
@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    """Add X-Process-Time header to all responses"""
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    response.headers["X-Process-Time"] = str(process_time)
    return response


# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Handle all uncaught exceptions"""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "detail": str(exc) if settings.DEBUG else "An unexpected error occurred"
        }
    )


# Include API routes
app.include_router(api_v1_router, prefix="/api/v1")


# Root endpoint
@app.get("/")
async def root():
    """Root endpoint with API information"""
    return {
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "status": "operational",
        "docs": "/docs",
        "api": "/api/v1"
    }


# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    from datetime import datetime
    from app.utils.health import check_services, is_healthy

    services = await check_services()

    return {
        "status": "healthy" if is_healthy(services) else "degraded",
        "timestamp": datetime.now().isoformat(),
        "services": services
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG
    )
