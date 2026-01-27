"""
Health check endpoints
"""
from fastapi import APIRouter
from datetime import datetime

from app.models.schemas import HealthCheckResponse
from app.utils.health import check_services

router = APIRouter()


@router.get("/", response_model=HealthCheckResponse)
async def health_check():
    """
    Comprehensive health check

    Checks connectivity to:
    - PostgreSQL database
    - Redis cache
    - MinIO/S3 storage
    - External APIs (optional)
    """
    services = await check_services()

    # Determine overall status
    status = "healthy" if all(s == "ok" for s in services.values()) else "degraded"

    return HealthCheckResponse(
        status=status,
        timestamp=datetime.now(),
        services=services
    )
