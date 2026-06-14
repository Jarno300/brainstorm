from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
import uuid


class TopicResponse(BaseModel):
    id: uuid.UUID
    brainstorm_id: uuid.UUID
    name: str
    description: str
    library_path: str
    created_at: datetime
    confidence: float
    is_proposition: bool

    class Config:
        from_attributes = True


class TopicEdgeResponse(BaseModel):
    id: uuid.UUID
    source_topic_id: uuid.UUID
    target_topic_id: uuid.UUID
    relationship: str
    weight: float
    source_name: str = ""
    target_name: str = ""

    class Config:
        from_attributes = True


class SuggestionResponse(BaseModel):
    """A proposition topic connected to its parent (source) topic."""
    id: uuid.UUID
    name: str
    description: str
    source_topic_id: uuid.UUID
    source_topic_name: str


class TopicRenameRequest(BaseModel):
    name: str


class MapConnectionCreateRequest(BaseModel):
    source_topic_id: uuid.UUID
    target_topic_id: uuid.UUID


class MapDataResponse(BaseModel):
    topics: List[TopicResponse]
    edges: List[TopicEdgeResponse]
    suggestions: List[SuggestionResponse] = []
