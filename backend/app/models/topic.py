import uuid
from sqlalchemy import Column, String, DateTime, Text, ForeignKey, Float, Boolean, Index
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.sqlite import JSON as SQLiteJSON
from sqlalchemy.types import TypeDecorator, UUID
from sqlalchemy.orm import relationship
from app.database import Base, utcnow


class FlexibleJSON(TypeDecorator):
    """JSONB on PostgreSQL, JSON on SQLite — for cross-dialect compatibility."""
    impl = JSONB
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "sqlite":
            return dialect.type_descriptor(SQLiteJSON())
        return dialect.type_descriptor(JSONB())


class Topic(Base):
    __tablename__ = "topics"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    brainstorm_id = Column(UUID(as_uuid=True), ForeignKey("brainstorms.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(255), nullable=False, index=True)
    description = Column(Text, default="")
    library_path = Column(String(500), default="")
    created_at = Column(DateTime, default=utcnow, index=True)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)
    confidence = Column(Float, default=0.0, index=True)
    is_proposition = Column(Boolean, default=False, index=True)
    position_x = Column(Float, default=0.0)
    position_y = Column(Float, default=0.0)
    outline = Column(FlexibleJSON, nullable=True, default=None)
    taxonomy = Column(FlexibleJSON, nullable=True, default=None)

    brainstorm = relationship("Brainstorm", back_populates="topics")

    __table_args__ = (
        Index("ix_topics_brainstorm_proposition", brainstorm_id, is_proposition),
    )
