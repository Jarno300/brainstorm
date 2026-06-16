from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
import uuid


class MessageCreate(BaseModel):
    content: str
    role: str = "user"


class MessageResponse(BaseModel):
    id: uuid.UUID
    brainstorm_id: uuid.UUID
    role: str
    content: str
    created_at: datetime

    class Config:
        from_attributes = True


class PaginatedMessagesResponse(BaseModel):
    """Cursor-based paginated response for messages."""
    messages: List[MessageResponse]
    has_more: bool
    before_id: Optional[str] = None  # Cursor to pass for the previous page
