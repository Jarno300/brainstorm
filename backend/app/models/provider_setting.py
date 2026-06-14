import uuid
from sqlalchemy import Column, String, DateTime, Text
from sqlalchemy.dialects.postgresql import UUID
from app.database import Base, utcnow


class ProviderSetting(Base):
    """Runtime provider configuration — API keys, base URLs.

    Stored per provider. Values are read at runtime and take priority
    over environment variables, which take priority over defaults.
    """
    __tablename__ = "provider_settings"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    provider = Column(String(50), unique=True, nullable=False, index=True)
    api_key = Column(Text, default="")
    base_url = Column(String(500), default="")
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)
