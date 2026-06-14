from pydantic import BaseModel
from typing import Optional
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
