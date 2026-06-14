import json
import uuid

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.database import SessionLocal
from app.services.brainstorm_service import get_brainstorm
from app.services.realtime_service import brainstorm_event_channel, create_async_redis_client

router = APIRouter(prefix="/api", tags=["realtime"])


@router.websocket("/ws/{brainstorm_id}")
async def brainstorm_updates(websocket: WebSocket, brainstorm_id: uuid.UUID):
    db = SessionLocal()
    redis_client = create_async_redis_client()
    pubsub = redis_client.pubsub()

    try:
        brainstorm = get_brainstorm(db, brainstorm_id)
        if not brainstorm:
            await websocket.close(code=4404)
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
