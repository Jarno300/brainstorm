from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
import uuid
from datetime import datetime, timezone

from app.database import get_db
from app.schemas.topic import (
    MapDataResponse, TopicResponse, TopicEdgeResponse, SuggestionResponse,
    TopicUpdateRequest, TopicCreateRequest,
)
from app.services import topic_service, brainstorm_service, message_service
from app.services.map_suggestion_service import rebuild_map_suggestions
from app.services.library_service import create_library_entry
from app.api.auth import get_current_user
from app.models.user import User
from app.models.topic import Topic
from app.models.topic_edge import TopicEdge

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


# ─── Topic CRUD ───────────────────────────────────────────────

@router.patch("/{brainstorm_id}/topics/{topic_id}", response_model=TopicResponse)
def update_topic(
    brainstorm_id: uuid.UUID,
    topic_id: uuid.UUID,
    data: TopicUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    brainstorm = brainstorm_service.get_brainstorm(db, brainstorm_id, user_id=current_user.id)
    if not brainstorm:
        raise HTTPException(status_code=404, detail="Brainstorm not found")

    topic = topic_service.get_topic(db, topic_id)
    if not topic or topic.brainstorm_id != brainstorm_id:
        raise HTTPException(status_code=404, detail="Topic not found")

    if data.name is not None:
        topic.name = data.name
    if data.description is not None:
        topic.description = data.description
    db.commit()
    db.refresh(topic)
    return topic


@router.delete("/{brainstorm_id}/topics/{topic_id}", status_code=204)
def delete_topic(
    brainstorm_id: uuid.UUID,
    topic_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    brainstorm = brainstorm_service.get_brainstorm(db, brainstorm_id, user_id=current_user.id)
    if not brainstorm:
        raise HTTPException(status_code=404, detail="Brainstorm not found")

    topic = topic_service.get_topic(db, topic_id)
    if not topic or topic.brainstorm_id != brainstorm_id:
        raise HTTPException(status_code=404, detail="Topic not found")

    # Delete associated edges first
    db.query(TopicEdge).filter(
        (TopicEdge.source_topic_id == topic_id) | (TopicEdge.target_topic_id == topic_id)
    ).delete(synchronize_session=False)
    db.delete(topic)
    db.commit()

    # Refresh suggestions now that this topic is gone
    rebuild_map_suggestions(db, brainstorm_id)
    return None


@router.post("/{brainstorm_id}/topics", response_model=TopicResponse, status_code=201)
def create_topic_manual(
    brainstorm_id: uuid.UUID,
    data: TopicCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    brainstorm = brainstorm_service.get_brainstorm(db, brainstorm_id, user_id=current_user.id)
    if not brainstorm:
        raise HTTPException(status_code=404, detail="Brainstorm not found")

    # Check for duplicate name
    existing = topic_service.get_topic_by_name(db, brainstorm_id, data.name, is_proposition=False)
    if existing:
        raise HTTPException(status_code=409, detail="A topic with this name already exists")

    topic_name = data.name.lower().replace(" ", "-")
    topic = topic_service.create_topic(
        db, brainstorm_id,
        name=topic_name,
        description=data.description,
        is_proposition=False,
        confidence=0.5,
    )

    # Create edges to all existing main topics (weak "related" edges)
    main_topics = [t for t in topic_service.get_topics(db, brainstorm_id)
                   if not t.is_proposition and t.id != topic.id]
    for other in main_topics:
        topic_service.create_edge(
            db, brainstorm_id,
            source_topic_id=topic.id,
            target_topic_id=other.id,
            relationship="related",
            weight=0.3,
        )

    # Generate a library entry for the new topic
    try:
        conv_text = _get_brainstorm_conversation_text(db, brainstorm_id)
        md_content = conv_text if conv_text.strip() else f"# {topic_name}\n\n*Manually created topic.*"
        file_name = f"{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.md"
        entry = create_library_entry(
            db, brainstorm_id,
            topic_id=topic.id,
            folder_name=topic_name,
            file_name=file_name,
            content=md_content,
        )
        topic.library_path = entry.file_path
        db.commit()
        db.refresh(topic)
    except Exception:
        pass  # Library entry is best-effort

    # Refresh suggestions
    rebuild_map_suggestions(db, brainstorm_id)
    return topic


@router.post("/{brainstorm_id}/topics/{topic_id}/explore", response_model=MapDataResponse)
def explore_topic(
    brainstorm_id: uuid.UUID,
    topic_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Deepen a topic: generate library entry and refresh suggestions for it."""
    brainstorm = brainstorm_service.get_brainstorm(db, brainstorm_id, user_id=current_user.id)
    if not brainstorm:
        raise HTTPException(status_code=404, detail="Brainstorm not found")

    topic = topic_service.get_topic(db, topic_id)
    if not topic or topic.brainstorm_id != brainstorm_id:
        raise HTTPException(status_code=404, detail="Topic not found")

    # Generate a library entry from the existing conversation
    conv_text = _get_brainstorm_conversation_text(db, brainstorm_id)
    # Use the conversation as the library content — it IS the research
    md_content = conv_text if conv_text.strip() else f"# {topic.name}\n\n*No conversation content yet.*"
    file_name = f"{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.md"
    entry = create_library_entry(
        db, brainstorm_id,
        topic_id=topic.id,
        folder_name=topic.name,
        file_name=file_name,
        content=md_content,
    )
    topic.library_path = entry.file_path
    topic.confidence = max(topic.confidence or 0.0, 0.7)
    db.commit()
    db.refresh(topic)

    # Rebuild suggestions
    rebuild_map_suggestions(db, brainstorm_id)
    return _build_map_response(db, brainstorm_id)


def _get_brainstorm_conversation_text(db: Session, brainstorm_id: uuid.UUID) -> str:
    """Build conversation text from stored messages."""
    messages = message_service.get_messages(db, brainstorm_id)
    parts = []
    for msg in messages:
        role_label = "User" if msg.role.value == "user" else "Assistant"
        parts.append(f"{role_label}: {msg.content}")
    return "\n\n".join(parts)
