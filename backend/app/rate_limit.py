"""
Rate-limiting middleware using Redis sliding-window counters.

Limits are configured per route prefix. Each request appends a timestamp
to a Redis sorted set keyed by client IP + route; entries outside the
window are trimmed before checking.
"""

import time
import logging
from typing import Callable

import redis
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from app.config import REDIS_URL

logger = logging.getLogger(__name__)

# ─── Per-route limits ────────────────────────────────────────
# (route_prefix, window_seconds, max_requests)
_ROUTE_LIMITS: list[tuple[str, int, int]] = [
    ("/api/auth/login", 60, 10),       # 10 login attempts per minute
    ("/api/auth/register", 3600, 5),   # 5 registrations per hour
    ("/api/chat/", 60, 30),            # 30 chat messages per minute
    ("/api/brainstorms", 60, 60),      # 60 CRUD ops per minute
]

# ─── Fallback for unmatched routes ───────────────────────────
_DEFAULT_WINDOW = 60
_DEFAULT_MAX = 120


def _get_limits(path: str) -> tuple[int, int]:
    """Return (window_seconds, max_requests) for the given path."""
    for prefix, window, max_req in _ROUTE_LIMITS:
        if path.startswith(prefix):
            return window, max_req
    return _DEFAULT_WINDOW, _DEFAULT_MAX


def _rate_limit_key(request: Request) -> str:
    """Build a Redis key scoped to client IP and route prefix."""
    client_ip = request.client.host if request.client else "unknown"
    # Use the route path without query params for grouping
    path = request.url.path
    return f"ratelimit:{client_ip}:{path}"


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Redis-backed sliding-window rate limiter.

    Skips WebSocket upgrade requests (those are handled separately).
    Returns 429 with Retry-After header when limit is exceeded.
    """

    def __init__(self, app, redis_url: str = REDIS_URL):
        super().__init__(app)
        self._redis_url = redis_url

    def _get_redis(self) -> redis.Redis:
        return redis.Redis.from_url(self._redis_url, decode_responses=True)

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Skip WebSocket upgrade requests (not rate-limited here)
        if request.headers.get("upgrade", "").lower() == "websocket":
            return await call_next(request)

        window, max_req = _get_limits(request.url.path)
        key = _rate_limit_key(request)
        now = time.time()
        window_start = now - window

        client = self._get_redis()
        try:
            pipe = client.pipeline()
            # Remove timestamps outside the current window
            pipe.zremrangebyscore(key, 0, window_start)
            # Count requests still in the window
            pipe.zcard(key)
            _, count = pipe.execute()

            if count and int(count) >= max_req:
                retry_after = int(window - (now - window_start))
                return JSONResponse(
                    status_code=429,
                    content={"detail": "Too many requests. Please slow down."},
                    headers={"Retry-After": str(max(retry_after, 1))},
                )

            # Record this request
            client.zadd(key, {str(now): now})
            client.expire(key, window + 2)

        except redis.RedisError as e:
            # If Redis is down, allow the request through — don't block users
            # because of rate-limit infrastructure failure.
            logger.warning("Rate-limit Redis error (failing open): %s", e)
        finally:
            client.close()

        return await call_next(request)
