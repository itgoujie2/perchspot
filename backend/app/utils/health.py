"""
Health check utilities
"""
import logging
from typing import Dict

logger = logging.getLogger(__name__)


async def check_services() -> Dict[str, str]:
    """
    Check health of all dependent services

    Returns:
        Dict mapping service name to status ('ok' or 'error')
    """
    services = {}

    # Check MySQL database
    try:
        from sqlalchemy import text
        from app.database.connection import engine
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        services["mysql"] = "ok"
    except Exception as e:
        logger.error(f"MySQL health check failed: {e}")
        services["mysql"] = "error"

    # Check Redis
    try:
        import redis
        from app.config import settings
        r = redis.from_url(settings.REDIS_URL)
        r.ping()
        services["redis"] = "ok"
    except Exception as e:
        logger.error(f"Redis health check failed: {e}")
        services["redis"] = "error"

    # Check MinIO/S3
    try:
        import boto3
        from app.config import settings
        s3 = boto3.client(
            's3',
            endpoint_url=settings.S3_ENDPOINT,
            aws_access_key_id=settings.S3_ACCESS_KEY,
            aws_secret_access_key=settings.S3_SECRET_KEY
        )
        s3.list_buckets()
        services["s3"] = "ok"
    except Exception as e:
        logger.error(f"S3/MinIO health check failed: {e}")
        services["s3"] = "error"

    # Check Qdrant
    try:
        from qdrant_client import QdrantClient
        from app.config import settings
        qclient = QdrantClient(url=settings.QDRANT_URL, timeout=5)
        qclient.get_collections()
        services["qdrant"] = "ok"
    except Exception as e:
        logger.error(f"Qdrant health check failed: {e}")
        services["qdrant"] = "error"

    return services
