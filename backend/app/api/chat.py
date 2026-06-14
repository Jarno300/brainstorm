import logging
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
import uuid

from app.database import get_db

logger = logging.getLogger(__name__)
from app.schemas.chat import ChatRequest, ChatResponse
from app.services import message_service, brainstorm_service
from app.services.ai_service import chat_with_model_sync, resolve_model_spec
from app.models.provider_setting import ProviderSetting
from app.tasks.classification_tasks import process_message_classification
from app.api.auth import get_current_user
from app.models.user import User

router = APIRouter(prefix="/api/chat", tags=["chat"])


@router.post("/", response_model=ChatResponse)
def chat(request: ChatRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    # Verify brainstorm exists
    brainstorm = brainstorm_service.get_brainstorm(db, request.brainstorm_id, user_id=current_user.id)
    if not brainstorm:
        raise HTTPException(status_code=404, detail="Brainstorm not found")

    # Save user message
    user_msg = message_service.create_message(
        db, request.brainstorm_id, "user", request.message
    )

    # Get conversation history
    messages = message_service.get_messages(db, request.brainstorm_id)
    chat_messages = [
        {"role": msg.role.value, "content": msg.content}
        for msg in messages
    ]

    # Get AI response
    try:
        model = request.model or brainstorm.model

        # Resolve API key and base URL: request override → DB setting → env var
        resolved = resolve_model_spec(model)
        api_key = request.api_key
        base_url = request.base_url

        if not api_key or not base_url:
            db_setting = db.query(ProviderSetting).filter(
                ProviderSetting.provider == resolved.provider
            ).first()
            if db_setting:
                if not api_key and db_setting.api_key:
                    api_key = db_setting.api_key
                if not base_url and db_setting.base_url:
                    base_url = db_setting.base_url

        ai_response = chat_with_model_sync(
            chat_messages, model,
            api_key=api_key,
            base_url=base_url,
        )
    except Exception as e:
        error_message = str(e)
        if "Maybe your model is not found" in error_message or "OllamaEndpointNotFoundError" in type(e).__name__:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=(
                    f"Configured model '{request.model or brainstorm.model}' is unavailable. "
                    "Pull the model in Ollama or choose a different model. "
                    f"{error_message}"
                ),
            )

        raise HTTPException(status_code=500, detail=f"AI model error: {error_message}")

    # Save AI response
    ai_msg = message_service.create_message(
        db, request.brainstorm_id, "assistant", ai_response
    )

    # Build the topic/library/map artifacts asynchronously via Celery.
    # The Celery worker publishes a Redis event when done;
    # the frontend WebSocket listener triggers map+library refresh.
    try:
        process_message_classification.delay(str(request.brainstorm_id))
    except Exception as e:
        logger.warning("Failed to dispatch classification task (non-fatal): %s", e)

    return ChatResponse(
        message_id=ai_msg.id,
        response=ai_response,
    )
