import uuid
from sqlalchemy import Column, String, DateTime, ForeignKey, Float, Integer, Text, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.database import Base, utcnow


class Flashcard(Base):
    """A flashcard generated from topic cards for spaced repetition review.

    Uses the SM-2 (SuperMemo 2) algorithm fields:
      - ease_factor: starts at 2.5, adjusts based on review quality
      - interval: days until next review (starts at 1)
      - repetitions: number of consecutive correct reviews
      - next_review: UTC datetime of when this card is due next
      - last_reviewed: UTC datetime of the most recent review
    """

    __tablename__ = "flashcards"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    brainstorm_id = Column(UUID(as_uuid=True), ForeignKey("brainstorms.id", ondelete="CASCADE"), nullable=False, index=True)
    topic_id = Column(UUID(as_uuid=True), ForeignKey("topics.id", ondelete="SET NULL"), nullable=True, index=True)
    question = Column(Text, nullable=False)
    answer = Column(Text, nullable=False)
    ease_factor = Column(Float, default=2.5, nullable=False)
    interval = Column(Integer, default=1, nullable=False)
    repetitions = Column(Integer, default=0, nullable=False)
    next_review = Column(DateTime, default=utcnow, nullable=False, index=True)
    last_reviewed = Column(DateTime, nullable=True, default=None)
    created_at = Column(DateTime, default=utcnow, nullable=False)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)

    brainstorm = relationship("Brainstorm")

    __table_args__ = (
        Index("ix_flashcards_brainstorm_due", brainstorm_id, next_review),
    )
