from pydantic import BaseModel
from typing import Optional
from datetime import datetime
import uuid


class BrainstormCreate(BaseModel):
    title: Optional[str] = "New Brainstorm"
    model: Optional[str] = "ollama/llama3.2:1b"


class BrainstormModelUpdate(BaseModel):
    model: str


class BrainstormResponse(BaseModel):
    id: uuid.UUID
    title: str
    created_at: datetime
    updated_at: datetime
    model: str
    is_active: bool
    summary: str

    class Config:
        from_attributes = True


class BrainstormListItem(BaseModel):
    id: uuid.UUID
    title: str
    created_at: datetime
    updated_at: datetime
    message_count: int = 0
    explored_topic_count: int = 0

    class Config:
        from_attributes = True
