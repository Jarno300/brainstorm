"""Public share endpoints — read-only access via share token, no auth required."""
import uuid
import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List

from app.database import get_db
from app.models.topic import Topic
from app.models.topic_edge import TopicEdge
from app.models.library_entry import LibraryEntry
from app.services.brainstorm_service import (
    generate_share_token,
    revoke_share_token,
    get_brainstorm_by_share_token,
    get_brainstorm,
)
from app.api.auth import get_current_user
from app.models.user import User

logger = logging.getLogger(__name__)

router = APIRouter(tags=["share"])


# ─── Schemas ─────────────────────────────────────────────────

class ShareResponse(BaseModel):
    share_url: str


class SharedTopic(BaseModel):
    id: str
    name: str
    description: str
    confidence: float


class SharedEdge(BaseModel):
    source: str
    target: str
    relationship: str
    weight: float


class SharedLibraryEntry(BaseModel):
    folder_name: str
    file_name: str
    content: str


class SharedBrainstormResponse(BaseModel):
    id: str
    title: str
    summary: str
    topics: List[SharedTopic]
    edges: List[SharedEdge]
    libraries: List[SharedLibraryEntry]


# ─── Auth-required: manage share tokens ──────────────────────

@router.post("/api/brainstorms/{brainstorm_id}/share")
def enable_sharing(brainstorm_id: uuid.UUID, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Generate or return a share token for a brainstorm."""
    token = generate_share_token(db, brainstorm_id, current_user.id)
    if not token:
        raise HTTPException(status_code=404, detail="Brainstorm not found")
    host = "http://localhost:5173"  # will be configurable
    return ShareResponse(share_url=f"{host}/shared/{token}")


@router.delete("/api/brainstorms/{brainstorm_id}/share")
def disable_sharing(brainstorm_id: uuid.UUID, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Revoke a share token."""
    revoked = revoke_share_token(db, brainstorm_id, current_user.id)
    if not revoked:
        raise HTTPException(status_code=404, detail="Brainstorm not found")
    return {"status": "ok"}


# ─── Public endpoints (no auth) ──────────────────────────────

@router.get("/api/share/{token}")
def get_shared_brainstorm(token: uuid.UUID, db: Session = Depends(get_db)):
    """View a published brainstorm in read-only mode."""
    brainstorm = get_brainstorm_by_share_token(db, token)
    if not brainstorm:
        raise HTTPException(status_code=404, detail="Brainstorm not found or not published")

    topics = db.query(Topic).filter(Topic.brainstorm_id == brainstorm.id).all()
    edges = db.query(TopicEdge).filter(TopicEdge.brainstorm_id == brainstorm.id).all()
    libraries = db.query(LibraryEntry).filter(LibraryEntry.brainstorm_id == brainstorm.id).all()

    return SharedBrainstormResponse(
        id=str(brainstorm.id),
        title=brainstorm.title,
        summary=brainstorm.summary,
        topics=[SharedTopic(id=str(t.id), name=t.name, description=t.description, confidence=t.confidence) for t in topics if not t.is_proposition],
        edges=[SharedEdge(source=str(e.source_topic_id), target=str(e.target_topic_id), relationship=e.relationship, weight=e.weight) for e in edges if e.relationship != "suggestion"],
        libraries=[SharedLibraryEntry(folder_name=l.folder_name, file_name=l.file_name, content=l.content) for l in libraries],
    )
