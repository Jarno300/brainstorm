"""Search API endpoint."""

import logging
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Optional

from app.database import get_db
from app.services.search_service import search
from app.api.auth import get_current_user
from app.models.user import User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/search", tags=["search"])


class SearchBrainstormHit(BaseModel):
    id: str
    title: str
    summary: str


class SearchMessageHit(BaseModel):
    id: str
    brainstorm_id: str
    brainstorm_title: str
    role: str
    snippet: str
    created_at: str


class SearchLibraryHit(BaseModel):
    id: str
    brainstorm_id: str
    brainstorm_title: str
    folder_name: str
    file_name: str
    snippet: str


class SearchResponse(BaseModel):
    brainstorms: List[SearchBrainstormHit]
    messages: List[SearchMessageHit]
    library: List[SearchLibraryHit]
    query: str
    total: int


@router.get("/", response_model=SearchResponse)
def search_endpoint(
    q: str = Query(..., min_length=2, description="Search query"),
    limit: int = Query(30, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Full-text search across brainstorms, messages, and library entries."""
    results = search(db, q, current_user.id, limit=limit)

    total = (
        len(results["brainstorms"])
        + len(results["messages"])
        + len(results["library"])
    )

    return SearchResponse(
        brainstorms=results["brainstorms"],
        messages=results["messages"],
        library=results["library"],
        query=q,
        total=total,
    )
