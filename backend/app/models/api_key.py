"""API Key model — user-created tokens for programmatic access."""

import uuid
import secrets
from sqlalchemy import Column, String, DateTime, Boolean, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.database import Base, utcnow


class ApiKey(Base):
    __tablename__ = "api_keys"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(100), nullable=False)  # user-given label
    key_prefix = Column(String(8), nullable=False)  # first 8 chars for display
    key_hash = Column(String(128), nullable=False, unique=True)  # bcrypt hash of full key
    scopes = Column(String(500), default="read write")  # space-separated scopes
    is_active = Column(Boolean, default=True)
    last_used_at = Column(DateTime, nullable=True, default=None)
    created_at = Column(DateTime, default=utcnow)

    user = relationship("User")

    @staticmethod
    def generate():
        """Generate a new API key and its hash."""
        raw = "bsk_" + secrets.token_urlsafe(32)
        import bcrypt
        key_hash = bcrypt.hashpw(raw.encode(), bcrypt.gensalt()).decode()
        key_prefix = raw[:11]  # "bsk_" + first 7 chars
        return raw, key_prefix, key_hash

    @staticmethod
    def verify(key: str, stored_hash: str) -> bool:
        """Verify a raw key against a stored hash."""
        import bcrypt
        try:
            return bcrypt.checkpw(key.encode(), stored_hash.encode())
        except Exception:
            return False
