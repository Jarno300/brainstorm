from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
import uuid


class FlashcardResponse(BaseModel):
    id: uuid.UUID
    brainstorm_id: uuid.UUID
    topic_id: Optional[uuid.UUID] = None
    question: str
    answer: str
    ease_factor: float
    interval: int
    repetitions: int
    next_review: datetime
    last_reviewed: Optional[datetime] = None
    created_at: datetime

    class Config:
        from_attributes = True


class FlashcardReviewRequest(BaseModel):
    """User rates the flashcard quality: 0 (complete blackout) to 5 (perfect)."""
    quality: int = Field(..., ge=0, le=5, description="0=blackout, 1=incorrect but remembered, 2=incorrect but easy recall, 3=correct with difficulty, 4=correct with hesitation, 5=perfect")


class FlashcardListResponse(BaseModel):
    flashcards: list[FlashcardResponse]
    total: int
    due_count: int
