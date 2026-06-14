import uuid
from sqlalchemy import Column, String, DateTime, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.database import Base, utcnow


class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    tier = Column(String(50), default="free", index=True)
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)

    # Relationships
    brainstorms = relationship("Brainstorm", back_populates="user", cascade="all, delete-orphan", passive_deletes=True)

    __table_args__ = (
        Index("ix_users_email_tier", email, tier),
    )