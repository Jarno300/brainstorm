from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
import uuid

from app.database import get_db
from app.schemas.topic import MapDataResponse, TopicResponse, TopicEdgeResponse, SuggestionResponse
from app.services import topic_service, brainstorm_service
from app.services.map_suggestion_service import rebuild_map_suggestions
from app.api.auth import get_current_user
from app.models.user import User

router = APIRouter(prefix="/api/map", tags=["map"])


def _build_map_response(db: Session, brainstorm_id: uuid.UUID) -> MapDataResponse:
    """Helper to build a full MapDataResponse with edge names and suggestions."""
    topics = topic_service.get_topics(db, brainstorm_id)
    edges = topic_service.get_edges(db, brainstorm_id)

    # Build topic id → name lookup
    topic_map = {t.id: t for t in topics}

    # Populate source_name / target_name on edges
    edge_responses = []
    for e in edges:
        source = topic_map.get(e.source_topic_id)
        target = topic_map.get(e.target_topic_id)
        edge_responses.append(TopicEdgeResponse(
            id=e.id,
            source_topic_id=e.source_topic_id,
            target_topic_id=e.target_topic_id,
            relationship=e.relationship,
            weight=e.weight,
            source_name=source.name if source else "",
            target_name=target.name if target else "",
        ))

    # Build suggestions list: proposition topics → their parent via suggestion edges
    suggestion_edges = [e for e in edges if e.relationship == "suggestion"]
    suggestions = []
    for se in suggestion_edges:
        prop = topic_map.get(se.target_topic_id)
        source = topic_map.get(se.source_topic_id)
        if prop and source and prop.is_proposition:
            suggestions.append(SuggestionResponse(
                id=prop.id,
                name=prop.name,
                description=prop.description,
                source_topic_id=source.id,
                source_topic_name=source.name,
            ))

    return MapDataResponse(
        topics=[TopicResponse.model_validate(t) for t in topics],
        edges=edge_responses,
        suggestions=suggestions,
    )


@router.get("/{brainstorm_id}", response_model=MapDataResponse)
def get_map(brainstorm_id: uuid.UUID, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    brainstorm = brainstorm_service.get_brainstorm(db, brainstorm_id, user_id=current_user.id)
    if not brainstorm:
        raise HTTPException(status_code=404, detail="Brainstorm not found")

    return _build_map_response(db, brainstorm_id)


@router.post("/{brainstorm_id}/refresh", response_model=MapDataResponse)
def refresh_propositions(brainstorm_id: uuid.UUID, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    brainstorm = brainstorm_service.get_brainstorm(db, brainstorm_id, user_id=current_user.id)
    if not brainstorm:
        raise HTTPException(status_code=404, detail="Brainstorm not found")

    rebuild_map_suggestions(db, brainstorm_id)

    # Return updated map
    return _build_map_response(db, brainstorm_id)
