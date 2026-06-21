"""Flashcards API — generation (streaming) and spaced repetition review."""

import json
import uuid
import logging

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.database import get_db, run_in_db
from app.api.auth import get_current_user
from app.models.user import User
from app.schemas.flashcard import (
    FlashcardResponse,
    FlashcardReviewRequest,
    FlashcardListResponse,
)
from app.services import brainstorm_service
from app.services.flashcard_service import (
    get_flashcards,
    get_due_flashcards,
    get_flashcard,
    apply_review,
    count_due,
    build_map_context,
    parse_flashcards_from_response,
    persist_flashcards,
    delete_flashcards_for_brainstorm,
    FLASHCARD_GENERATION_PROMPT,
)
from app.services.ai_service import (
    stream_chat_with_model,
    resolve_credentials,
)
from app.services.realtime_service import publish_brainstorm_event

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/map", tags=["flashcards"])


@router.get("/{brainstorm_id}/flashcards", response_model=FlashcardListResponse)
def list_flashcards(
    brainstorm_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all flashcards for a brainstorm with due count."""
    brainstorm = brainstorm_service.get_brainstorm(db, brainstorm_id, user_id=current_user.id)
    if not brainstorm:
        raise HTTPException(status_code=404, detail="Brainstorm not found")

    cards = get_flashcards(db, brainstorm_id)
    due = count_due(db, brainstorm_id)

    return FlashcardListResponse(
        flashcards=[FlashcardResponse.model_validate(c) for c in cards],
        total=len(cards),
        due_count=due,
    )


@router.get("/{brainstorm_id}/flashcards/due", response_model=FlashcardListResponse)
def list_due_flashcards(
    brainstorm_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List only flashcards that are due for review."""
    brainstorm = brainstorm_service.get_brainstorm(db, brainstorm_id, user_id=current_user.id)
    if not brainstorm:
        raise HTTPException(status_code=404, detail="Brainstorm not found")

    cards = get_due_flashcards(db, brainstorm_id)

    return FlashcardListResponse(
        flashcards=[FlashcardResponse.model_validate(c) for c in cards],
        total=len(cards),
        due_count=len(cards),
    )


@router.post("/{brainstorm_id}/flashcards/generate")
def generate_flashcards(
    brainstorm_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Generate flashcards from the knowledge map via LLM.

    Streams tokens via SSE. On completion, persists the parsed flashcards
    to the database and emits a 'flashcards_generated' WebSocket event.

    Existing flashcards for this brainstorm are deleted before generation.
    """
    brainstorm = brainstorm_service.get_brainstorm(db, brainstorm_id, user_id=current_user.id)
    if not brainstorm:
        raise HTTPException(status_code=404, detail="Brainstorm not found")

    # Build map context
    map_context = build_map_context(db, brainstorm_id)
    if map_context.strip() == "(empty map)":
        raise HTTPException(status_code=400, detail="No topic cards in this map to generate flashcards from")

    prompt = FLASHCARD_GENERATION_PROMPT.format(map_content=map_context)
    model = brainstorm.model
    api_key, base_url = resolve_credentials(db, model)

    async def event_stream():
        full_response = ""
        try:
            async for token in stream_chat_with_model(
                [{"role": "user", "content": prompt}],
                model,
                api_key=api_key,
                base_url=base_url,
            ):
                full_response += token
                yield f"data: {json.dumps({'token': token})}\n\n"
        except Exception as e:
            logger.error("Flashcard generation stream error for brainstorm %s: %s", brainstorm_id, e)
            yield f"data: {json.dumps({'error': str(e)})}\n\n"
            return

        if not full_response.strip():
            yield f"data: {json.dumps({'done': True, 'error': 'Empty response from model'})}\n\n"
            return

        # Parse and persist via thread-pool executor
        try:
            result = await run_in_db(
                lambda db: _persist_generated_flashcards(db, brainstorm_id, full_response)
            )
            yield f"data: {json.dumps({'done': True, **result})}\n\n"
        except Exception as e:
            logger.error("Failed to persist flashcards for brainstorm %s: %s", brainstorm_id, e)
            yield f"data: {json.dumps({'error': f'Failed to save flashcards: {e}'})}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


def _persist_generated_flashcards(
    db: Session,
    brainstorm_id: uuid.UUID,
    full_response: str,
) -> dict:
    """Parse LLM response and persist flashcards in a fresh DB session."""
    cards = parse_flashcards_from_response(full_response)

    if not cards:
        return {"count": 0, "error": "No flashcards could be parsed from the response"}

    # Delete existing flashcards for this brainstorm
    delete_flashcards_for_brainstorm(db, brainstorm_id, commit=False)

    # Persist new cards
    count = persist_flashcards(db, brainstorm_id, cards)

    # Publish WebSocket event
    publish_brainstorm_event(
        "flashcards_generated",
        brainstorm_id,
        {"count": count},
    )

    return {"count": count}


@router.post("/{brainstorm_id}/flashcards/{flashcard_id}/review", response_model=FlashcardResponse)
def review_flashcard(
    brainstorm_id: uuid.UUID,
    flashcard_id: uuid.UUID,
    data: FlashcardReviewRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Record a spaced repetition review for a flashcard.

    Accepts a quality rating 0-5 and updates the SM-2 scheduling fields
    (ease_factor, interval, repetitions, next_review).
    """
    brainstorm = brainstorm_service.get_brainstorm(db, brainstorm_id, user_id=current_user.id)
    if not brainstorm:
        raise HTTPException(status_code=404, detail="Brainstorm not found")

    card = get_flashcard(db, flashcard_id)
    if not card or card.brainstorm_id != brainstorm_id:
        raise HTTPException(status_code=404, detail="Flashcard not found")

    updated = apply_review(db, flashcard_id, data.quality)
    if not updated:
        raise HTTPException(status_code=500, detail="Failed to update flashcard")

    publish_brainstorm_event(
        "flashcard_reviewed",
        brainstorm_id,
        {
            "flashcard_id": str(flashcard_id),
            "quality": data.quality,
            "next_review": updated.next_review.isoformat(),
        },
    )

    return FlashcardResponse.model_validate(updated)
