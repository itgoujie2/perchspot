"""
Health check utilities — resilient with per-service timeouts.

Optional services (Qdrant, MinIO) can be slow/down without failing the health check.
Only MySQL being unreachable makes the backend "unhealthy".
"""
import asyncio
import logging
from typing import Dict

logger = logging.getLogger(__name__)

SERVICE_CHECK_TIMEOUT = 3  # seconds per service


async def _check_mysql() -> str:
    from sqlalchemy import text
    from app.database.connection import engine
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    return "ok"


async def _check_redis() -> str:
    import redis
    from app.config import settings
    r = redis.from_url(settings.REDIS_URL)
    r.ping()
    return "ok"


async def _check_s3() -> str:
    import boto3
    from app.config import settings
    s3 = boto3.client(
        's3',
        endpoint_url=settings.S3_ENDPOINT,
        aws_access_key_id=settings.S3_ACCESS_KEY,
        aws_secret_access_key=settings.S3_SECRET_KEY
    )
    s3.list_buckets()
    return "ok"


async def _run_check(name: str, coro) -> tuple[str, str]:
    """Run a single service check with a timeout."""
    try:
        result = await asyncio.wait_for(coro(), timeout=SERVICE_CHECK_TIMEOUT)
        return name, result
    except asyncio.TimeoutError:
        logger.warning(f"{name} health check timed out ({SERVICE_CHECK_TIMEOUT}s)")
        return name, "timeout"
    except Exception as e:
        logger.error(f"{name} health check failed: {e}")
        return name, "error"


async def check_services() -> Dict[str, str]:
    """
    Check health of all dependent services concurrently with timeouts.

    Returns:
        Dict mapping service name to status ('ok', 'timeout', or 'error')
    """
    checks = [
        _run_check("mysql", _check_mysql),
        _run_check("redis", _check_redis),
        _run_check("s3", _check_s3),
    ]

    results = await asyncio.gather(*checks)
    return dict(results)


# Services that must be healthy for the backend to be considered operational.
# Qdrant and S3/MinIO are optional — analysis degrades but login/admin still work.
CRITICAL_SERVICES = {"mysql", "redis"}


def is_healthy(services: Dict[str, str]) -> bool:
    """Return True if all critical services are ok."""
    return all(services.get(s) == "ok" for s in CRITICAL_SERVICES)
