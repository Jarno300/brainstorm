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
from app.services.realtime_service import publish_brainstorm_event, invalidate_map_cache

logger = logging.getLogger(__name__)


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

    # Invalidate the map cache so the frontend sees the new topics
    invalidate_map_cache(brainstorm_id)

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
# Connection exploration task (thin Celery wrapper)
# ═══════════════════════════════════════════════════════════════
# Core logic lives in app.services.connection_exploration_service

from app.services.connection_exploration_service import explore_connection


def process_connection_exploration_sync(
    brainstorm_id_str: str,
    source_topic_id_str: str,
    target_topic_id_str: str,
    position_x: float,
    position_y: float,
) -> dict:
    """Synchronous fallback for connection exploration.

    Used when Celery/Redis is unavailable. Opens a fresh DB session
    and calls the shared service logic.
    """
    brainstorm_id = uuid.UUID(brainstorm_id_str)
    with task_session() as db:
        return explore_connection(
            db, brainstorm_id,
            uuid.UUID(source_topic_id_str),
            uuid.UUID(target_topic_id_str),
            position_x, position_y,
        )


@celery_app.task(bind=True, max_retries=2)
def process_connection_exploration(
    self,
    brainstorm_id_str: str,
    source_topic_id_str: str,
    target_topic_id_str: str,
    position_x: float,
    position_y: float,
) -> dict:
    """Celery task: generate connection explanation between two topics.

    Thin wrapper — delegates to connection_exploration_service.
    """
    brainstorm_id = uuid.UUID(brainstorm_id_str)

    try:
        with task_session() as db:
            return explore_connection(
                db, brainstorm_id,
                uuid.UUID(source_topic_id_str),
                uuid.UUID(target_topic_id_str),
                position_x, position_y,
            )
    except Exception as e:
        error_type = type(e).__name__
        error_msg = str(e)[:500]
        logger.error(
            "connection_exploration error | brainstorm=%s error=%s",
            brainstorm_id, error_msg,
        )
        publish_brainstorm_event("classification_error", brainstorm_id, {
            "error": error_msg,
            "stage": "connection",
            "type": error_type,
        })
        return {"status": "error", "error": error_msg}
