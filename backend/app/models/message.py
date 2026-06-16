import uuid
import enum

from sqlalchemy import Column, String, DateTime, Text, ForeignKey, Enum as SAEnum, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.database import Base, utcnow
from app.json_type import JSONType


class MessageRole(str, enum.Enum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class Message(Base):
    __tablename__ = "messages"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    brainstorm_id = Column(UUID(as_uuid=True), ForeignKey("brainstorms.id", ondelete="CASCADE"), nullable=False, index=True)
    role = Column(SAEnum(MessageRole), nullable=False, index=True)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=utcnow, index=True)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)
    metadata_json = Column(JSONType, default=dict)
    # Branching support
    branch_id = Column(UUID(as_uuid=True), nullable=True, index=True, default=None)
    parent_message_id = Column(UUID(as_uuid=True), ForeignKey("messages.id", ondelete="SET NULL"), nullable=True, index=True, default=None)

    brainstorm = relationship("Brainstorm", back_populates="messages")
    parent_message = relationship("Message", remote_side="Message.id", backref="children")

    __table_args__ = (
        Index("ix_messages_brainstorm_created", brainstorm_id, created_at),
        Index("ix_messages_brainstorm_branch", brainstorm_id, branch_id),
    )
