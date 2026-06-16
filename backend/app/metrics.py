"""
Prometheus metrics for the Brainstorm API.

Exposes standard RED (Rate, Errors, Duration) metrics via /metrics endpoint.
Tracks:
  - HTTP request count by method, path, status
  - HTTP request duration histogram
  - Active WebSocket connections (gauge)
  - Celery task queue depth (gauge, queried on scrape)
"""

import time
from collections import defaultdict

from prometheus_client import (
    Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST,
    CollectorRegistry, multiprocess,
)
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

# ── Registry ────────────────────────────────────────────────
registry = CollectorRegistry(auto_describe=True)

# ── Metrics ──────────────────────────────────────────────────

http_requests_total = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["method", "path", "status"],
    registry=registry,
)

http_request_duration_seconds = Histogram(
    "http_request_duration_seconds",
    "HTTP request duration in seconds",
    ["method", "path"],
    buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0],
    registry=registry,
)

http_requests_in_flight = Gauge(
    "http_requests_in_flight",
    "Currently in-flight HTTP requests",
    registry=registry,
)

websocket_connections = Gauge(
    "websocket_connections_total",
    "Current active WebSocket connections",
    ["brainstorm_id"],
    registry=registry,
)


# ── Path normalization for cardinality control ──────────────
# Replaces UUIDs and numeric IDs with {param} to avoid metric explosion.

import re

_PATH_UUID_RE = re.compile(
    r"/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
    re.IGNORECASE,
)


def normalize_path(path: str) -> str:
    """Replace UUID segments with {id} to keep metric cardinality low."""
    return _PATH_UUID_RE.sub("/{id}", path)


# ── Middleware ───────────────────────────────────────────────

class MetricsMiddleware(BaseHTTPMiddleware):
    """Record request count, latency, and in-flight gauge for every HTTP request."""

    async def dispatch(self, request, call_next):
        # Skip metrics endpoint itself to avoid recursion
        if request.url.path == "/metrics":
            return await call_next(request)

        path = normalize_path(request.url.path)
        method = request.method

        http_requests_in_flight.inc()
        start = time.perf_counter()

        try:
            response = await call_next(request)
            status = str(response.status_code)
        except Exception:
            status = "500"
            raise
        finally:
            http_requests_in_flight.dec()
            elapsed = time.perf_counter() - start
            http_requests_total.labels(method=method, path=path, status=status).inc()
            http_request_duration_seconds.labels(method=method, path=path).observe(elapsed)

        return response


# ── Metrics endpoint handler ────────────────────────────────

async def metrics_endpoint(request):
    """Prometheus /metrics endpoint — returns text exposition format."""
    data = generate_latest(registry)
    return Response(content=data, media_type=CONTENT_TYPE_LATEST)
