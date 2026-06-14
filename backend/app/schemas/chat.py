from pydantic import BaseModel
from typing import Optional
import uuid


class ChatRequest(BaseModel):
    brainstorm_id: uuid.UUID
    message: str
    model: Optional[str] = None
    api_key: Optional[str] = None       # runtime override for API key
    base_url: Optional[str] = None      # runtime override for base URL


class ChatResponse(BaseModel):
    message_id: uuid.UUID
    response: str
