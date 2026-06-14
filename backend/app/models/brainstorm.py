import uuid
from sqlalchemy import Column, String, DateTime, Boolean, Text, ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.database import Base, utcnow


class Brainstorm(Base):
    __tablename__ = "brainstorms"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)
    title = Column(String(255), default="New Brainstorm", index=True)
    created_at = Column(DateTime, default=utcnow, index=True)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)
    model = Column(String(100), default="ollama/llama3.2:1b")
    is_active = Column(Boolean, default=True)
    summary = Column(Text, default="")
    share_token = Column(UUID(as_uuid=True), nullable=True, unique=True, default=None, index=True)
    is_published = Column(Boolean, default=False)
    deleted_at = Column(DateTime, nullable=True, default=None, index=True)

    # Relationships
    user = relationship("User", back_populates="brainstorms")
    messages = relationship("Message", back_populates="brainstorm", cascade="all, delete-orphan", passive_deletes=True)
    topics = relationship("Topic", back_populates="brainstorm", cascade="all, delete-orphan", passive_deletes=True)
    topic_edges = relationship("TopicEdge", back_populates="brainstorm", cascade="all, delete-orphan", passive_deletes=True)
    library_entries = relationship("LibraryEntry", back_populates="brainstorm", cascade="all, delete-orphan", passive_deletes=True)
    suggestion_dismissals = relationship("MapSuggestionDismissal", back_populates="brainstorm", cascade="all, delete-orphan", passive_deletes=True)

    __table_args__ = (
        Index("ix_brainstorms_deleted_at_created", deleted_at, created_at),
    )
