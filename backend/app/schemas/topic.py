from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
import uuid


class OutlineSection(BaseModel):
    """A user-defined section title for a topic outline."""
    title: str = Field(..., min_length=1, max_length=255)


class TaxonomyItem(BaseModel):
    """A single taxonomy entry (parent/child/related topic)."""
    name: str
    description: str = ""


class TopicTaxonomy(BaseModel):
    """Structured taxonomy stored on a topic."""
    parent_topics: List[TaxonomyItem] = []
    child_topics: List[TaxonomyItem] = []
    related_topics: List[TaxonomyItem] = []


class TopicResponse(BaseModel):
    id: uuid.UUID
    brainstorm_id: uuid.UUID
    name: str
    description: str
    library_path: str
    created_at: datetime
    confidence: float
    is_proposition: bool
    position_x: float = 0.0
    position_y: float = 0.0
    outline: Optional[List[OutlineSection]] = None
    taxonomy: Optional[TopicTaxonomy] = None

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


class TopicUpdateRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    position_x: Optional[float] = None
    position_y: Optional[float] = None
    outline: Optional[List[OutlineSection]] = None


class TopicCreateRequest(BaseModel):
    name: str
    description: str = ""
    outline: Optional[List[OutlineSection]] = None
    auto_generate: bool = True


class EdgeCreateRequest(BaseModel):
    source_topic_id: uuid.UUID
    target_topic_id: uuid.UUID
    relationship: str = "related"
    weight: float = 0.5


class MapDataResponse(BaseModel):
    topics: List[TopicResponse]
    edges: List[TopicEdgeResponse]
    suggestions: List[SuggestionResponse] = []
