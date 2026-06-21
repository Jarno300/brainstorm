import uuid
from sqlalchemy import Column, String, DateTime, Text, ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.database import Base, utcnow


class LibraryEntry(Base):
    __tablename__ = "library_entries"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    brainstorm_id = Column(UUID(as_uuid=True), ForeignKey("brainstorms.id", ondelete="CASCADE"), nullable=False, index=True)
    topic_id = Column(UUID(as_uuid=True), ForeignKey("topics.id", ondelete="SET NULL"), nullable=True, index=True)
    folder_name = Column(String(255), nullable=False, index=True)
    file_name = Column(String(255), nullable=False)
    file_path = Column(String(500), nullable=True, default="")
    content = Column(Text, default="")
    source_type = Column(String(50), nullable=True, default=None)  # 'chat', 'upload', 'research', 'explore', 'connection'
    source_id = Column(String(255), nullable=True, default=None)   # message_id, file_id, etc.
    source_model = Column(String(100), nullable=True, default=None)  # LLM model used
    created_at = Column(DateTime, default=utcnow, index=True)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)

    brainstorm = relationship("Brainstorm", back_populates="library_entries")

    __table_args__ = (
        Index("ix_library_brainstorm_folder", brainstorm_id, folder_name),
    )
