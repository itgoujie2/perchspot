"""
Celery Beat monitoring tasks.

- check_qps_threshold: alerts when RPM exceeds warning/critical thresholds
- check_backend_health: alerts when the backend /health endpoint is slow or down
"""
import time
import logging

import redis
import requests

from app.tasks.celery_app import celery_app
from app.config import settings

logger = logging.getLogger(__name__)

RPM_WARNING_THRESHOLD = 50
RPM_CRITICAL_THRESHOLD = 100
HEALTH_URL = "http://backend:8000/health"
HEALTH_TIMEOUT = 5  # seconds


def _get_alert_service():
    """Lazy import to avoid circular imports at module level."""
    from app.services.monitoring.alert_service import AlertService
    return AlertService()


@celery_app.task(name="check_qps_threshold", ignore_result=True)
def check_qps_threshold():
    """Read the previous minute's RPM from Redis and alert if above threshold."""
    try:
        r = redis.Redis.from_url(settings.REDIS_URL, decode_responses=True)
        prev_minute = int(time.time()) // 60 - 1
        key = f"metrics:rpm:{prev_minute}"
        rpm = int(r.get(key) or 0)
    except Exception as e:
        logger.warning(f"QPS check: Redis error: {e}")
        return

    logger.info(f"QPS check: {rpm} requests/min")

    if rpm >= RPM_CRITICAL_THRESHOLD:
        alert = _get_alert_service()
        alert.send_alert(
            alert_type="qps_critical",
            subject=f"CRITICAL: {rpm} requests/min",
            body_text=(
                f"Request volume is critically high.\n\n"
                f"  RPM: {rpm}\n"
                f"  Threshold: {RPM_CRITICAL_THRESHOLD}\n\n"
                f"Check for abuse or DDoS activity."
            ),
            cooldown=15 * 60,
        )
    elif rpm >= RPM_WARNING_THRESHOLD:
        alert = _get_alert_service()
        alert.send_alert(
            alert_type="qps_warning",
            subject=f"Warning: {rpm} requests/min",
            body_text=(
                f"Request volume is elevated.\n\n"
                f"  RPM: {rpm}\n"
                f"  Threshold: {RPM_WARNING_THRESHOLD}\n\n"
                f"Monitor for further increases."
            ),
            cooldown=15 * 60,
        )


@celery_app.task(name="check_backend_health", ignore_result=True)
def check_backend_health():
    """Hit the backend /health endpoint and alert on problems."""
    start = time.time()

    try:
        resp = requests.get(HEALTH_URL, timeout=HEALTH_TIMEOUT)
        elapsed = time.time() - start
    except requests.exceptions.ConnectionError as e:
        alert = _get_alert_service()
        alert.send_alert(
            alert_type="health_connection_error",
            subject="Backend unreachable",
            body_text=(
                f"Could not connect to {HEALTH_URL}.\n\n"
                f"  Error: {e}\n\n"
                f"The backend container may be down or restarting."
            ),
            cooldown=5 * 60,
        )
        logger.error(f"Health check: connection error: {e}")
        return
    except requests.exceptions.Timeout:
        alert = _get_alert_service()
        alert.send_alert(
            alert_type="health_timeout",
            subject=f"Backend health timeout (>{HEALTH_TIMEOUT}s)",
            body_text=(
                f"Health check to {HEALTH_URL} timed out after {HEALTH_TIMEOUT}s.\n\n"
                f"The server may be hung or overloaded."
            ),
            cooldown=5 * 60,
        )
        logger.error("Health check: timeout")
        return
    except Exception as e:
        logger.error(f"Health check: unexpected error: {e}")
        return

    # Non-200 status
    if resp.status_code != 200:
        alert = _get_alert_service()
        alert.send_alert(
            alert_type="health_non200",
            subject=f"Backend unhealthy (HTTP {resp.status_code})",
            body_text=(
                f"Health check returned HTTP {resp.status_code}.\n\n"
                f"  URL: {HEALTH_URL}\n"
                f"  Response time: {elapsed:.2f}s\n"
                f"  Body: {resp.text[:500]}"
            ),
            cooldown=5 * 60,
        )
        logger.warning(f"Health check: HTTP {resp.status_code}")
        return

    # Check for degraded status
    try:
        data = resp.json()
        status = data.get("status", "unknown")
    except Exception:
        status = "unknown"

    if status == "degraded":
        alert = _get_alert_service()
        alert.send_alert(
            alert_type="health_degraded",
            subject="Backend degraded",
            body_text=(
                f"Health check reports degraded status.\n\n"
                f"  URL: {HEALTH_URL}\n"
                f"  Response time: {elapsed:.2f}s\n"
                f"  Services: {data.get('services', 'N/A')}"
            ),
            cooldown=15 * 60,
        )
        logger.warning(f"Health check: degraded — {data.get('services')}")
        return

    # Slow response (but 200 OK + healthy)
    if elapsed > HEALTH_TIMEOUT:
        alert = _get_alert_service()
        alert.send_alert(
            alert_type="health_slow",
            subject=f"Backend slow ({elapsed:.1f}s)",
            body_text=(
                f"Health check succeeded but took {elapsed:.2f}s (threshold {HEALTH_TIMEOUT}s).\n\n"
                f"  URL: {HEALTH_URL}\n"
                f"  Status: {status}"
            ),
            cooldown=15 * 60,
        )
        logger.warning(f"Health check: slow response {elapsed:.2f}s")
        return

    logger.debug(f"Health check: OK ({elapsed:.2f}s)")
