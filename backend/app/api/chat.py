import json
import logging
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
import uuid

from app.database import get_db, run_in_db
from app.sanitize import sanitize_text

logger = logging.getLogger(__name__)
from app.schemas.chat import ChatRequest, ChatResponse
from app.services import message_service, brainstorm_service
from app.services.ai_service import (
    chat_with_model, stream_chat_with_model,
    resolve_credentials,
)
from app.tasks.classification_tasks import process_message_classification, process_message_classification_sync
from app.api.auth import get_current_user
from app.models.user import User

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("/", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Send a message and get a synchronous AI response.

    Returns the full response at once. For streaming, use `/chat/stream`.
    """
    # Verify brainstorm exists
    brainstorm = brainstorm_service.get_brainstorm(db, request.brainstorm_id, user_id=current_user.id)
    if not brainstorm:
        raise HTTPException(status_code=404, detail="Brainstorm not found")

    # Save user message (sanitized)
    clean_message = sanitize_text(request.message)
    if not clean_message:
        raise HTTPException(status_code=400, detail="Message cannot be empty")
    user_msg = message_service.create_message(
        db, request.brainstorm_id, "user", clean_message
    )

    # Get conversation history (recent messages for context)
    messages, _ = message_service.get_messages(db, request.brainstorm_id, limit=200)
    chat_messages = [
        {"role": msg.role.value, "content": msg.content}
        for msg in messages
    ]

    # Get AI response
    try:
        model = request.model or brainstorm.model
        api_key, base_url = resolve_credentials(db, model, request.api_key, request.base_url)

        ai_response = await chat_with_model(
            chat_messages, model,
            api_key=api_key,
            base_url=base_url,
        )
    except Exception as e:
        error_message = str(e)
        if "Maybe your model is not found" in error_message or "OllamaEndpointNotFoundError" in type(e).__name__:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="The configured model is unavailable. Pull the model in Ollama or choose a different model.",
            )

        raise HTTPException(
            status_code=500,
            detail="AI model error. Please check your model settings and try again.",
        )

    # Save AI response
    ai_msg = message_service.create_message(
        db, request.brainstorm_id, "assistant", ai_response
    )

    # Build the topic/library/map artifacts asynchronously via Celery.
    # Falls back to synchronous classification if Celery/Redis is unavailable.
    try:
        process_message_classification.delay(str(request.brainstorm_id))
    except Exception as e:
        logger.warning("Celery dispatch failed, running classification synchronously: %s", e)
        try:
            process_message_classification_sync(str(request.brainstorm_id))
        except Exception as sync_e:
            logger.error("Synchronous classification also failed: %s", sync_e)

    return ChatResponse(
        message_id=ai_msg.id,
        response=ai_response,
    )


@router.post("/stream")
async def chat_stream(
    request: ChatRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Send a message and stream the AI response via Server-Sent Events.

    Events:
    - `token`: A chunk of the response text
    - `done`: Streaming complete, includes full metadata
    - `error`: An error occurred
    """
    """Stream the AI response token-by-token via Server-Sent Events.

    The frontend receives tokens in real-time and assembles the full
    response. After the stream completes, the message is persisted and
    the classification Celery task is dispatched (same as /chat/).
    """
    # Verify brainstorm exists
    brainstorm = brainstorm_service.get_brainstorm(db, request.brainstorm_id, user_id=current_user.id)
    if not brainstorm:
        raise HTTPException(status_code=404, detail="Brainstorm not found")

    # Save user message (sanitized)
    clean_message = sanitize_text(request.message)
    if not clean_message:
        raise HTTPException(status_code=400, detail="Message cannot be empty")
    user_msg = message_service.create_message(
        db, request.brainstorm_id, "user", clean_message
    )

    # Get conversation history (recent messages for context)
    messages, _ = message_service.get_messages(db, request.brainstorm_id, limit=200)
    chat_messages = [
        {"role": msg.role.value, "content": msg.content}
        for msg in messages
    ]

    model = request.model or brainstorm.model
    api_key, base_url = resolve_credentials(db, model, request.api_key, request.base_url)

    async def event_stream():
        full_response = ""
        try:
            async for token in stream_chat_with_model(
                chat_messages, model,
                api_key=api_key,
                base_url=base_url,
            ):
                full_response += token
                yield f"data: {json.dumps({'token': token})}\n\n"
        except Exception as e:
            error_message = str(e)
            logger.error("Stream error: %s", error_message)
            yield f"data: {json.dumps({'error': error_message})}\n\n"
            return

        # Persist the AI message via thread-pool executor.
        if full_response:
            try:
                msg_id = await run_in_db(
                    lambda db: message_service.create_message(
                        db, request.brainstorm_id, "assistant", full_response
                    ).id
                )
                yield f"data: {json.dumps({'done': True, 'message_id': str(msg_id)})}\n\n"

                # Dispatch async classification with synchronous fallback
                try:
                    process_message_classification.delay(str(request.brainstorm_id))
                except Exception as e:
                    logger.warning("Celery dispatch failed, running classification synchronously: %s", e)
                    try:
                        process_message_classification_sync(str(request.brainstorm_id))
                    except Exception as sync_e:
                        logger.error("Synchronous classification also failed: %s", sync_e)
            except Exception as e:
                logger.error("Failed to persist chat message: %s", e)
                yield f"data: {json.dumps({'error': f'Failed to save message: {e}'})}\n\n"
        else:
            yield f"data: {json.dumps({'done': True, 'error': 'Empty response from model'})}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
