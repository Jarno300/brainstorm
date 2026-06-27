"""
Connection exploration service — generates LLM explanations of how two
topics connect, creates a connection card topic, and manages edges.

Extracted from tasks/research_tasks.py so the core logic is testable
independently of Celery.
"""

import logging
import uuid

from sqlalchemy.orm import Session

from app.services.topic_service import create_topic, create_edge, get_topic, get_topic_by_name
from app.services.brainstorm_service import get_brainstorm
from app.services.ai_service import chat_with_model_sync, resolve_credentials
from app.services.enrichment_service import create_topic_library_entry
from app.services.map_suggestion_service import rebuild_map_suggestions
from app.services.realtime_service import publish_brainstorm_event, invalidate_map_cache
from app.models.topic_edge import TopicEdge

logger = logging.getLogger(__name__)

# ── Prompt ───────────────────────────────────────────────────

CONNECTION_PROMPT = """You are a knowledgeable researcher. Explain how "{topic_a}" and "{topic_b}" are connected.

Structure your response as follows:

> A single-line summary of the connection between {topic_a} and {topic_b}.

## How They Connect
2-3 paragraphs explaining the relationship between these two topics. Cover:
- How they relate to or depend on each other
- Key similarities and differences
- Historical or conceptual links
- How one influences or enables the other

## Key Intersections
- **Intersection point**: Brief explanation
- **Intersection point**: Brief explanation
(2-3 entries)

## Related Topics
- topic-name-slug - How this broader topic relates to the connection
- another-topic-slug - Another related field
(1-2 entries)

Use markdown formatting. Be thorough and accurate. Start directly with the summary line."""


# ── Public API ────────────────────────────────────────────────

def explore_connection(
    db: Session,
    brainstorm_id: uuid.UUID,
    source_topic_id: uuid.UUID,
    target_topic_id: uuid.UUID,
    position_x: float = 0.0,
    position_y: float = 0.0,
) -> dict:
    """Generate an LLM explanation of how two topics connect.

    Creates a connection card topic, links it to both source/target with
    dashed edges, removes the original direct edge, creates a library
    entry, and publishes a WebSocket event.

    Args:
        db: Database session.
        brainstorm_id: Brainstorm UUID.
        source_topic_id: First topic in the connection.
        target_topic_id: Second topic in the connection.
        position_x: X position for the new connection card.
        position_y: Y position for the new connection card.

    Returns:
        {"connection_topic_id": str, "library_entry_id": str}
    """
    source = get_topic(db, source_topic_id)
    target = get_topic(db, target_topic_id)
    if not source or not target:
        raise ValueError("Source or target topic not found")
    if source.brainstorm_id != brainstorm_id or target.brainstorm_id != brainstorm_id:
        raise ValueError("Topics do not belong to this brainstorm")

    source_display = source.name.replace("-", " ").title()
    target_display = target.name.replace("-", " ").title()
    connection_name = f"{source.name}-{target.name}-connection"

    # Check for duplicate connection topic
    existing = get_topic_by_name(db, brainstorm_id, connection_name, is_proposition=False)
    if existing:
        raise ValueError("A connection topic between these two already exists")

    # Get model from brainstorm
    brainstorm = get_brainstorm(db, brainstorm_id)
    model = brainstorm.model if brainstorm else None
    api_key, base_url = resolve_credentials(db, model)

    # Generate connection content via LLM
    prompt = CONNECTION_PROMPT.format(topic_a=source_display, topic_b=target_display)
    try:
        raw = chat_with_model_sync(
            [{"role": "user", "content": prompt}],
            model=model,
            api_key=api_key,
            base_url=base_url,
        )
    except Exception as e:
        logger.error("Connection LLM call failed: %s", e)
        raise ValueError(f"Failed to generate connection content: {e}")

    # Parse summary (first line starting with "> ")
    lines = raw.split("\n")
    summary = ""
    if lines and lines[0].startswith("> "):
        summary = lines[0][2:].strip()

    # Create connection topic
    connection = create_topic(
        db, brainstorm_id,
        name=connection_name,
        description=summary or f"Connection between {source_display} and {target_display}",
        is_proposition=False,
        confidence=0.7,
        outline=None,
        commit=False,
    )
    connection.position_x = position_x
    connection.position_y = position_y

    # Create library entry
    entry = create_topic_library_entry(
        db, brainstorm_id,
        topic=connection,
        folder_name=connection_name,
        content=raw,
        source_type="connection",
        commit=False,
        publish_event=False,
    )

    # Create fixed edges from connection to both source and target
    create_edge(
        db, brainstorm_id,
        source_topic_id=connection.id,
        target_topic_id=source.id,
        relationship="connection_link",
        weight=0.5,
        commit=False,
    )
    create_edge(
        db, brainstorm_id,
        source_topic_id=connection.id,
        target_topic_id=target.id,
        relationship="connection_link",
        weight=0.5,
        commit=False,
    )

    # Remove the original direct edge between source and target
    db.query(TopicEdge).filter(
        TopicEdge.brainstorm_id == brainstorm_id,
        ((TopicEdge.source_topic_id == source.id) & (TopicEdge.target_topic_id == target.id))
        | ((TopicEdge.source_topic_id == target.id) & (TopicEdge.target_topic_id == source.id)),
    ).delete(synchronize_session=False)

    db.commit()
    invalidate_map_cache(brainstorm_id)
    db.refresh(connection)

    # Rebuild suggestions for the updated map
    rebuild_map_suggestions(db, brainstorm_id)

    # Notify frontend
    publish_brainstorm_event(
        "topic_generated",
        brainstorm_id,
        {
            "topic_id": str(connection.id),
            "library_entry_id": str(entry.id),
        },
    )

    logger.info(
        "connection_exploration done | brainstorm=%s source=%s target=%s connection=%s",
        brainstorm_id, source.name, target.name, connection.name,
    )

    return {
        "connection_topic_id": str(connection.id),
        "library_entry_id": str(entry.id),
    }
