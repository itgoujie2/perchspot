"""
Prometheus metrics middleware for FastAPI.

Tracks HTTP request count, duration, and in-progress requests.
Also pushes per-minute request counts to Redis for cross-worker QPS aggregation.
"""
import time
import re
import logging
from typing import Optional

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST

logger = logging.getLogger(__name__)

# --- Prometheus metrics ---

REQUEST_COUNT = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["method", "path_template", "status_code"],
)

REQUEST_DURATION = Histogram(
    "http_request_duration_seconds",
    "HTTP request duration in seconds",
    ["method", "path_template"],
    buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0),
)

REQUESTS_IN_PROGRESS = Gauge(
    "http_requests_in_progress",
    "HTTP requests currently in progress",
    ["method"],
)

# Path patterns to collapse into templates (order matters — first match wins)
_PATH_PATTERNS = [
    (re.compile(r"^/api/v1/analysis/stream/(.+)$"), "/api/v1/analysis/stream/{address}"),
    (re.compile(r"^/api/v1/analysis/(.+)$"), "/api/v1/analysis/{address}"),
    (re.compile(r"^/api/v1/admin/cached-reports/(.+)$"), "/api/v1/admin/cached-reports/{filename}"),
    (re.compile(r"^/api/v1/admin/promo-codes/(.+)$"), "/api/v1/admin/promo-codes/{code}"),
    (re.compile(r"^/api/v1/admin/users/([^/]+)/add-credits$"), "/api/v1/admin/users/{id}/add-credits"),
    (re.compile(r"^/api/v1/admin/users/(.+)$"), "/api/v1/admin/users/{id}"),
    (re.compile(r"^/api/v1/admin/analyses/(.+)$"), "/api/v1/admin/analyses/{id}"),
    (re.compile(r"^/api/v1/payments/success.*$"), "/api/v1/payments/success"),
]

# Paths to skip entirely (health/metrics probes)
_SKIP_PATHS = {"/health", "/metrics"}


def _normalize_path(path: str) -> str:
    """Collapse dynamic path segments into templates to avoid metric explosion."""
    for pattern, template in _PATH_PATTERNS:
        if pattern.match(path):
            return template
    return path


class MetricsMiddleware(BaseHTTPMiddleware):
    """Starlette middleware that records Prometheus metrics and Redis RPM counters."""

    def __init__(self, app, redis_url: Optional[str] = None):
        super().__init__(app)
        self._redis = None
        if redis_url:
            try:
                import redis
                self._redis = redis.Redis.from_url(redis_url, decode_responses=True)
                self._redis.ping()
                logger.info("MetricsMiddleware: Redis connected for RPM tracking")
            except Exception as e:
                logger.warning(f"MetricsMiddleware: Redis unavailable, RPM tracking disabled: {e}")
                self._redis = None

    async def dispatch(self, request: Request, call_next) -> Response:
        path = request.url.path
        method = request.method

        # Skip internal probes
        if path in _SKIP_PATHS:
            return await call_next(request)

        path_template = _normalize_path(path)

        REQUESTS_IN_PROGRESS.labels(method=method).inc()
        start = time.perf_counter()

        try:
            response = await call_next(request)
            status = response.status_code
        except Exception:
            status = 500
            raise
        finally:
            duration = time.perf_counter() - start
            REQUESTS_IN_PROGRESS.labels(method=method).dec()
            REQUEST_COUNT.labels(method=method, path_template=path_template, status_code=status).inc()
            REQUEST_DURATION.labels(method=method, path_template=path_template).observe(duration)

            # Redis per-minute bucket for QPS aggregation
            if self._redis:
                try:
                    minute_bucket = int(time.time()) // 60
                    key = f"metrics:rpm:{minute_bucket}"
                    pipe = self._redis.pipeline(transaction=False)
                    pipe.incr(key)
                    pipe.expire(key, 300)  # TTL 5 minutes — keep a few buckets around
                    pipe.execute()
                except Exception:
                    pass  # Never let metrics break requests

            # Add X-Process-Time header
            response.headers["X-Process-Time"] = f"{duration:.4f}"

        return response


def metrics_endpoint() -> Response:
    """Return Prometheus text-format metrics."""
    return Response(
        content=generate_latest(),
        media_type=CONTENT_TYPE_LATEST,
    )
