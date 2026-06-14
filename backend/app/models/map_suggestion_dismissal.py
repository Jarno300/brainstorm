import uuid

from sqlalchemy import Column, DateTime, ForeignKey, String, UniqueConstraint, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.database import Base, utcnow


class MapSuggestionDismissal(Base):
    __tablename__ = "map_suggestion_dismissals"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    brainstorm_id = Column(UUID(as_uuid=True), ForeignKey("brainstorms.id", ondelete="CASCADE"), nullable=False, index=True)
    source_topic_id = Column(UUID(as_uuid=True), ForeignKey("topics.id", ondelete="CASCADE"), nullable=False, index=True)
    suggestion_name = Column(String(255), nullable=False, index=True)
    created_at = Column(DateTime, default=utcnow, index=True)

    brainstorm = relationship("Brainstorm", back_populates="suggestion_dismissals")

    __table_args__ = (
        UniqueConstraint(
            "brainstorm_id",
            "source_topic_id",
            "suggestion_name",
            name="uq_map_suggestion_dismissal",
        ),
        Index("ix_suggestion_dismissals_brainstorm", brainstorm_id, created_at),
    )
