"""
Map service — knowledge map operations that were previously scattered
across API handlers (map.py). Extracted for testability and separation
of concerns.

Provides:
  - build_map_response      — assemble the full MapDataResponse
  - delete_topic             — delete a topic with connection card reconnection
  - delete_edge              — delete an edge by id
  - get_topic_comments       — fetch comments for a topic
  - get_conversation_text    — build conversation transcript from messages
"""

import logging
import uuid
from typing import List, Optional

from sqlalchemy.orm import Session

from app.models.topic import Topic
from app.models.topic_edge import TopicEdge
from app.models.message import Message
from app.schemas.topic import (
    MapDataResponse, TopicResponse, TopicEdgeResponse, SuggestionResponse,
)
from app.services import topic_service, message_service
from app.services.map_suggestion_service import rebuild_map_suggestions
from app.services.realtime_service import invalidate_map_cache

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════
# Map response builder
# ═══════════════════════════════════════════════════════════════

def build_map_response(db: Session, brainstorm_id: uuid.UUID) -> MapDataResponse:
    """Build a full MapDataResponse with topics, edges (with source/target names),
    and suggestion pills.

    Replaces the _build_map_response helper previously in map.py.
    """
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
    suggestion_edges = [e for e in edges if e.relationship.startswith("suggestion")]
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


# ═══════════════════════════════════════════════════════════════
# Topic deletion with connection card reconnection
# ═══════════════════════════════════════════════════════════════

def delete_topic(
    db: Session,
    brainstorm_id: uuid.UUID,
    topic: Topic,
    commit: bool = True,
) -> None:
    """Delete a topic and all its edges from the knowledge map.

    If the topic is a connection card (name ends in -connection),
    the two bridged topics are reconnected with a direct "related" edge
    before the connection card is removed.

    After deletion, suggestions are rebuilt and the map cache is invalidated.
    """
    topic_id = topic.id

    # If this is a connection card, reconnect the two bridged topics
    if topic.name.endswith("-connection"):
        connection_edges = db.query(TopicEdge).filter(
            TopicEdge.brainstorm_id == brainstorm_id,
            TopicEdge.relationship == "connection_link",
            (TopicEdge.source_topic_id == topic_id) | (TopicEdge.target_topic_id == topic_id),
        ).all()

        linked_topic_ids = []
        for edge in connection_edges:
            other_id = edge.target_topic_id if edge.source_topic_id == topic_id else edge.source_topic_id
            linked_topic_ids.append(other_id)

        # Recreate direct edge between the two bridged topics
        if len(linked_topic_ids) == 2:
            existing = db.query(TopicEdge).filter(
                TopicEdge.brainstorm_id == brainstorm_id,
                ((TopicEdge.source_topic_id == linked_topic_ids[0]) & (TopicEdge.target_topic_id == linked_topic_ids[1]))
                | ((TopicEdge.source_topic_id == linked_topic_ids[1]) & (TopicEdge.target_topic_id == linked_topic_ids[0])),
            ).first()
            if not existing:
                topic_service.create_edge(
                    db, brainstorm_id,
                    source_topic_id=linked_topic_ids[0],
                    target_topic_id=linked_topic_ids[1],
                    relationship="related",
                    weight=0.5,
                    commit=False,
                )

    # Delete associated edges first
    db.query(TopicEdge).filter(
        (TopicEdge.source_topic_id == topic_id) | (TopicEdge.target_topic_id == topic_id)
    ).delete(synchronize_session=False)

    db.delete(topic)

    if commit:
        db.commit()

    invalidate_map_cache(brainstorm_id)

    # Refresh suggestions now that this topic is gone
    rebuild_map_suggestions(db, brainstorm_id)

    logger.info("delete_topic done | brainstorm=%s topic_id=%s name=%s", brainstorm_id, topic_id, topic.name)


# ═══════════════════════════════════════════════════════════════
# Edge deletion
# ═══════════════════════════════════════════════════════════════

def delete_edge(
    db: Session,
    brainstorm_id: uuid.UUID,
    edge_id: uuid.UUID,
) -> Optional[TopicEdge]:
    """Delete an edge by id. Returns the deleted edge or None if not found."""
    edge = db.query(TopicEdge).filter(
        TopicEdge.id == edge_id,
        TopicEdge.brainstorm_id == brainstorm_id,
    ).first()

    if not edge:
        return None

    db.delete(edge)
    db.commit()
    invalidate_map_cache(brainstorm_id)

    return edge


# ═══════════════════════════════════════════════════════════════
# Topic comments
# ═══════════════════════════════════════════════════════════════

def get_topic_comments(db: Session, topic_id: uuid.UUID) -> List[Message]:
    """Get all comments on a topic, ordered by creation time."""
    return (
        db.query(Message)
        .filter(Message.topic_id == topic_id)
        .order_by(Message.created_at)
        .all()
    )


# ═══════════════════════════════════════════════════════════════
# Conversation text helper
# ═══════════════════════════════════════════════════════════════

def get_conversation_text(db: Session, brainstorm_id: uuid.UUID, limit: int = 200) -> str:
    """Build a conversation transcript from stored messages.

    Used when generating library content or taxonomy — provides context
    from the chat history to the LLM prompts.
    """
    messages, _ = message_service.get_messages(db, brainstorm_id, limit=limit)
    parts = []
    for msg in messages:
        role_label = "User" if msg.role.value == "user" else "Assistant"
        parts.append(f"{role_label}: {msg.content}")
    return "\n\n".join(parts)
