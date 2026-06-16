import json
import uuid

import redis
import redis.asyncio as redis_async

from app.config import REDIS_URL

# ── Shared Redis connection pool ────────────────────────────
# Reusing connections avoids creating/destroying on every publish.
_sync_pool: redis.ConnectionPool | None = None


def _get_sync_pool() -> redis.ConnectionPool:
    global _sync_pool
    if _sync_pool is None:
        _sync_pool = redis.ConnectionPool.from_url(REDIS_URL, decode_responses=True)
    return _sync_pool


def brainstorm_event_channel(brainstorm_id: uuid.UUID) -> str:
    return f"brainstorm:{brainstorm_id}:events"


def build_brainstorm_event(event_type: str, brainstorm_id: uuid.UUID, data: dict | None = None) -> dict:
    return {
        "event": event_type,
        "brainstorm_id": str(brainstorm_id),
        "data": data or {},
    }


def publish_brainstorm_event(event_type: str, brainstorm_id: uuid.UUID, data: dict | None = None) -> None:
    client = redis.Redis(connection_pool=_get_sync_pool())
    client.publish(
        brainstorm_event_channel(brainstorm_id),
        json.dumps(build_brainstorm_event(event_type, brainstorm_id, data)),
    )


def create_async_redis_client():
    return redis_async.Redis.from_url(REDIS_URL, decode_responses=True)
