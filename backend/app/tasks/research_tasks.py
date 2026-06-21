"""
Celery tasks for topic research and connection exploration.

Offloads synchronous LLM calls from the request-response cycle so
the FastAPI event loop stays free for other requests.

Two tasks:
  1. process_research — deep topic research + knowledge map building
  2. process_connection_exploration — generate explanation of how two topics connect

Both publish results via Redis PubSub (WebSocket events) so the frontend
can update the canvas asynchronously.
"""

import logging
import uuid
from datetime import datetime, timezone

from app.tasks.celery_app import celery_app
from app.database import task_session
from app.services.topic_research_service import research_topic, build_knowledge_map
from app.services.brainstorm_service import get_brainstorm
from app.services.ai_service import chat_with_model_sync, resolve_credentials
from app.services.topic_service import create_topic, create_edge, get_topic, get_topic_by_name
from app.services.library_service import create_library_entry
from app.services.map_suggestion_service import rebuild_map_suggestions
from app.services.realtime_service import publish_brainstorm_event, invalidate_map_cache
from app.models.topic_edge import TopicEdge

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════
# Connection exploration prompt
# ═══════════════════════════════════════════════════════════════

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


# ═══════════════════════════════════════════════════════════════
# Research task
# ═══════════════════════════════════════════════════════════════

def _execute_research(db, brainstorm_id: uuid.UUID, topic_name: str) -> dict:
    """Core research logic — shared by Celery task and sync fallback.

    Opens its own DB session (passed in) so it's self-contained.
    """
    brainstorm = get_brainstorm(db, brainstorm_id)
    if not brainstorm:
        raise ValueError(f"Brainstorm {brainstorm_id} not found")

    # Step 1: Research the topic via LLM
    result = research_topic(topic_name, model=brainstorm.model)
    if result is None:
        raise ValueError("Research failed — the model could not produce structured results")

    # Step 2: Build the knowledge map (topics, edges, library entry)
    primary = build_knowledge_map(db, brainstorm_id, topic_name, result, commit=True, model=brainstorm.model)

    # Step 3: Notify frontend via WebSocket
    props_count = sum(1 for _ in [
        result.parent_topics, result.child_topics, result.related_topics,
    ])
    publish_brainstorm_event(
        "classification_complete",
        brainstorm_id,
        {
            "status": "success",
            "topics_created": 1,
            "primary_topic": {
                "id": str(primary.id),
                "name": primary.name,
            },
        },
    )

    logger.info(
        "research_task done | brainstorm=%s topic=%s primary=%s",
        brainstorm_id, topic_name, primary.id,
    )

    return {
        "status": "success",
        "primary_topic_id": str(primary.id),
        "propositions_created": props_count,
    }


@celery_app.task(bind=True, max_retries=2)
def process_research(self, brainstorm_id_str: str, topic_name: str) -> dict:
    """Celery task: research a topic and build its knowledge map.

    Dispatched from POST /api/v1/research/{brainstorm_id}.
    Publishes classification_complete or classification_error via Redis PubSub.
    """
    brainstorm_id = uuid.UUID(brainstorm_id_str)

    try:
        with task_session() as db:
            return _execute_research(db, brainstorm_id, topic_name)

    except Exception as e:
        error_type = type(e).__name__
        error_msg = str(e)[:500]

        logger.error(
            "research_task error | brainstorm=%s topic=%s type=%s error=%s",
            brainstorm_id, topic_name, error_type, error_msg,
        )

        publish_brainstorm_event("classification_error", brainstorm_id, {
            "error": error_msg,
            "stage": "research",
            "type": error_type,
            "retry": self.request.retries < self.max_retries,
        })

        # Retry on transient errors
        if "timeout" in error_msg.lower() or "connection" in error_msg.lower():
            raise self.retry(exc=e, countdown=30)

        return {"status": "error", "error": error_msg}


def process_research_sync(brainstorm_id_str: str, topic_name: str) -> dict:
    """Synchronous fallback for when Celery/Redis is unavailable.

    Runs the full research pipeline inline — blocks the calling thread
    but keeps the feature working when the task queue is down.
    """
    brainstorm_id = uuid.UUID(brainstorm_id_str)
    with task_session() as db:
        return _execute_research(db, brainstorm_id, topic_name)


# ═══════════════════════════════════════════════════════════════
# Connection exploration task
# ═══════════════════════════════════════════════════════════════

def _execute_connection_exploration(
    db,
    brainstorm_id: uuid.UUID,
    source_topic_id: uuid.UUID,
    target_topic_id: uuid.UUID,
    position_x: float,
    position_y: float,
) -> dict:
    """Core connection exploration logic — shared by Celery task and sync fallback.

    Generates an LLM explanation of how two topics connect, creates a
    connection card topic, links it to both source/target, and removes
    the original direct edge.
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
    file_name = f"{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.md"
    entry = create_library_entry(
        db, brainstorm_id,
        topic_id=connection.id,
        folder_name=connection_name,
        file_name=file_name,
        content=raw.strip(),
        source_type="connection",
        commit=False,
    )
    connection.library_path = entry.file_path

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
        "status": "success",
        "connection_topic_id": str(connection.id),
        "connection_name": connection.name,
        "summary": summary,
    }


@celery_app.task(bind=True, max_retries=2)
def process_connection_exploration(
    self,
    brainstorm_id_str: str,
    source_topic_id_str: str,
    target_topic_id_str: str,
    position_x: float,
    position_y: float,
) -> dict:
    """Celery task: generate a connection card between two topics.

    Dispatched from POST /api/v1/map/{brainstorm_id}/explore-connection.
    Publishes topic_generated or classification_error via Redis PubSub.
    """
    brainstorm_id = uuid.UUID(brainstorm_id_str)
    source_topic_id = uuid.UUID(source_topic_id_str)
    target_topic_id = uuid.UUID(target_topic_id_str)

    try:
        with task_session() as db:
            return _execute_connection_exploration(
                db, brainstorm_id, source_topic_id, target_topic_id,
                position_x, position_y,
            )

    except Exception as e:
        error_type = type(e).__name__
        error_msg = str(e)[:500]

        logger.error(
            "connection_exploration error | brainstorm=%s source=%s target=%s type=%s error=%s",
            brainstorm_id, source_topic_id, target_topic_id, error_type, error_msg,
        )

        publish_brainstorm_event("classification_error", brainstorm_id, {
            "error": error_msg,
            "stage": "connection_exploration",
            "type": error_type,
            "retry": self.request.retries < self.max_retries,
        })

        if "timeout" in error_msg.lower() or "connection" in error_msg.lower():
            raise self.retry(exc=e, countdown=30)

        return {"status": "error", "error": error_msg}


def process_connection_exploration_sync(
    brainstorm_id_str: str,
    source_topic_id_str: str,
    target_topic_id_str: str,
    position_x: float,
    position_y: float,
) -> dict:
    """Synchronous fallback for when Celery/Redis is unavailable."""
    brainstorm_id = uuid.UUID(brainstorm_id_str)
    source_topic_id = uuid.UUID(source_topic_id_str)
    target_topic_id = uuid.UUID(target_topic_id_str)
    with task_session() as db:
        return _execute_connection_exploration(
            db, brainstorm_id, source_topic_id, target_topic_id,
            position_x, position_y,
        )
