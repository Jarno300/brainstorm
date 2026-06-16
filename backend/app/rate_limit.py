"""
Rate-limiting middleware using Redis sliding-window counters.

Limits are configured per route prefix. Each request appends a timestamp
to a Redis sorted set keyed by client IP + route; entries outside the
window are trimmed before checking.
"""

import logging
import time
from typing import Callable

import jwt
import redis
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from app.config import REDIS_URL, SECRET_KEY, JWT_ALGORITHM

logger = logging.getLogger(__name__)

# ─── Tier-based multipliers ─────────────────────────────────
TIER_MULTIPLIERS = {
    "free": 1.0,
    "premium": 3.0,
    "pro": 5.0,
}

# ─── Redis connection pool (shared across all requests) ─────
# Creating a new connection per request exhausts Redis under load.
# This pool is lazily initialized on first use.
_pool: redis.ConnectionPool | None = None


def _get_redis_pool() -> redis.ConnectionPool:
    """Return a shared Redis connection pool, creating it if needed."""
    global _pool
    if _pool is None:
        _pool = redis.ConnectionPool.from_url(REDIS_URL, decode_responses=True)
    return _pool

# ─── Per-route limits ────────────────────────────────────────
# (route_prefix, window_seconds, max_requests)
_ROUTE_LIMITS: list[tuple[str, int, int]] = [
    ("/api/v1/auth/login", 60, 10),
    ("/api/auth/login", 60, 10),         # backward compat
    ("/api/v1/auth/register", 3600, 5),
    ("/api/auth/register", 3600, 5),      # backward compat
    ("/api/v1/chat/", 60, 30),
    ("/api/chat/", 60, 30),               # backward compat
    ("/api/v1/brainstorms", 60, 60),
    ("/api/brainstorms", 60, 60),          # backward compat
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


def _extract_tier(request: Request) -> str:
    """Extract user tier from the Authorization header without DB lookup.

    Decodes the JWT to read the 'tier' claim. Returns 'free' on any failure
    so that unauthenticated/malformed tokens get the default limits.
    """
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return "free"
    try:
        token = auth.split(" ", 1)[1]
        payload = jwt.decode(token, SECRET_KEY, algorithms=[JWT_ALGORITHM])
        return str(payload.get("tier", "free")).lower()
    except Exception:
        return "free"


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Redis-backed sliding-window rate limiter.

    Skips WebSocket upgrade requests (those are handled separately).
    Returns 429 with Retry-After header when limit is exceeded.
    """

    def __init__(self, app, redis_url: str = REDIS_URL):
        super().__init__(app)
        # Ensure the shared pool is initialized
        _get_redis_pool()

    def _get_redis(self) -> redis.Redis:
        return redis.Redis(connection_pool=_get_redis_pool())

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Skip WebSocket upgrade requests (not rate-limited here)
        if request.headers.get("upgrade", "").lower() == "websocket":
            return await call_next(request)

        window, max_req = _get_limits(request.url.path)
        tier = _extract_tier(request)
        multiplier = TIER_MULTIPLIERS.get(tier, 1.0)
        effective_max = int(max_req * multiplier)
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

            if count and int(count) >= effective_max:
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
