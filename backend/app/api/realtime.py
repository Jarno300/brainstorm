import json
import uuid

import jwt
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query

from app.config import REDIS_URL, SECRET_KEY, JWT_ALGORITHM
from app.database import SessionLocal
from app.services.brainstorm_service import get_brainstorm
from app.services.realtime_service import brainstorm_event_channel, create_async_redis_client

router = APIRouter(prefix="/api", tags=["realtime"])


async def _authenticate_ws(websocket: WebSocket, token: str | None) -> dict | None:
    """Validate the JWT token from WebSocket query params.

    Returns the decoded payload on success, or closes the connection
    with 4001 and returns None on failure.
    """
    if not token:
        await websocket.close(code=4001, reason="Missing authentication token")
        return None
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[JWT_ALGORITHM])
        if not payload.get("sub"):
            await websocket.close(code=4001, reason="Invalid token payload")
            return None
        return payload
    except jwt.ExpiredSignatureError:
        await websocket.close(code=4001, reason="Token expired")
        return None
    except jwt.InvalidTokenError:
        await websocket.close(code=4001, reason="Invalid token")
        return None


@router.websocket("/ws/{brainstorm_id}")
async def brainstorm_updates(
    websocket: WebSocket,
    brainstorm_id: uuid.UUID,
    token: str | None = Query(None),
):
    # Authenticate before accepting the connection
    user_payload = await _authenticate_ws(websocket, token)
    if user_payload is None:
        return

    db = SessionLocal()
    redis_client = create_async_redis_client()
    pubsub = redis_client.pubsub()

    try:
        brainstorm = get_brainstorm(db, brainstorm_id)
        if not brainstorm:
            await websocket.close(code=4404, reason="Brainstorm not found")
            return

        # Scope to the authenticated user's own brainstorms
        if str(brainstorm.user_id) != user_payload["sub"]:
            await websocket.close(code=4403, reason="Access denied")
            return

        await websocket.accept()
        await pubsub.subscribe(brainstorm_event_channel(brainstorm_id))

        await websocket.send_text(json.dumps({"event": "CONNECTED", "brainstorm_id": str(brainstorm_id)}))

        async for message in pubsub.listen():
            if message.get("type") != "message":
                continue
            await websocket.send_text(message["data"])
    except WebSocketDisconnect:
        pass
    finally:
        try:
            await pubsub.unsubscribe(brainstorm_event_channel(brainstorm_id))
        except Exception:
            pass
        await pubsub.close()
        await redis_client.close()
        db.close()
