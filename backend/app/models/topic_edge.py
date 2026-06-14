import uuid
from sqlalchemy import Column, String, DateTime, ForeignKey, Float, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship as orm_relationship
from app.database import Base, utcnow


class TopicEdge(Base):
    __tablename__ = "topic_edges"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    brainstorm_id = Column(UUID(as_uuid=True), ForeignKey("brainstorms.id", ondelete="CASCADE"), nullable=False, index=True)
    source_topic_id = Column(UUID(as_uuid=True), ForeignKey("topics.id", ondelete="CASCADE"), nullable=False, index=True)
    target_topic_id = Column(UUID(as_uuid=True), ForeignKey("topics.id", ondelete="CASCADE"), nullable=False, index=True)
    relationship = Column(String(255), default="related", index=True)
    weight = Column(Float, default=1.0)
    created_at = Column(DateTime, default=utcnow, index=True)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)

    brainstorm = orm_relationship("Brainstorm", back_populates="topic_edges")

    __table_args__ = (
        Index("ix_topic_edges_source_target", source_topic_id, target_topic_id),
        Index("ix_topic_edges_brainstorm_rel", brainstorm_id, relationship),
    )
