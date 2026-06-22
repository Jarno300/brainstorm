from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse, JSONResponse
from sqlalchemy.orm import Session
import asyncio
import uuid
import json
from datetime import datetime, timezone

from app.database import get_db, run_in_db
from app.schemas.topic import (
    MapDataResponse, TopicResponse, TopicEdgeResponse, SuggestionResponse,
    TopicUpdateRequest, TopicCreateRequest, EdgeCreateRequest,
)
from app.services import topic_service, brainstorm_service
from app.services.map_suggestion_service import rebuild_map_suggestions
from app.services.realtime_service import (
    publish_brainstorm_event, cache_map, get_cached_map, invalidate_map_cache,
)
from app.services.library_service import create_library_entry
from app.services.gap_detection_service import detect_gaps
from app.services.topic_enrichment_service import (
    generate_library_content,
    generate_topic_taxonomy,
)
from app.services import map_service
from app.api.auth import get_current_user
from app.models.user import User
from app.sanitize import sanitize_topic_name, sanitize_topic_description
from pydantic import BaseModel, Field
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/map", tags=["map"])


@router.get("/{brainstorm_id}", response_model=MapDataResponse)
def get_map(
    brainstorm_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get the full knowledge map including topics, edges, and suggestions.

    Uses a short-lived Redis cache (5s TTL) to avoid rebuilding the
    response on every drag/save during canvas editing.
    """
    brainstorm = brainstorm_service.get_brainstorm(db, brainstorm_id, user_id=current_user.id)
    if not brainstorm:
        raise HTTPException(status_code=404, detail="Brainstorm not found")

    # Try Redis cache first (best-effort — fails silently if Redis is down)
    cached = get_cached_map(brainstorm_id)
    if cached is not None:
        return cached

    response = map_service.build_map_response(db, brainstorm_id)
    cache_map(brainstorm_id, response.model_dump())
    return response


@router.post("/{brainstorm_id}/refresh", response_model=MapDataResponse)
def refresh_propositions(brainstorm_id: uuid.UUID, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    brainstorm = brainstorm_service.get_brainstorm(db, brainstorm_id, user_id=current_user.id)
    if not brainstorm:
        raise HTTPException(status_code=404, detail="Brainstorm not found")

    rebuild_map_suggestions(db, brainstorm_id)
    invalidate_map_cache(brainstorm_id)

    # Return updated map
    return map_service.build_map_response(db, brainstorm_id)


class GapItem(BaseModel):
    type: str
    topic_id: str | None = None
    topic_name: str | None = None
    related_topic_id: str | None = None
    related_topic_name: str | None = None
    message: str
    action: str


class GapDetectionResponse(BaseModel):
    gaps: list[GapItem]
    total: int


@router.get("/{brainstorm_id}/gaps", response_model=GapDetectionResponse)
def get_gaps(
    brainstorm_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Detect knowledge gaps in the map: orphans, disconnected clusters,
    missing taxonomy dimensions, and poorly connected topics."""
    brainstorm = brainstorm_service.get_brainstorm(db, brainstorm_id, user_id=current_user.id)
    if not brainstorm:
        raise HTTPException(status_code=404, detail="Brainstorm not found")

    gaps = detect_gaps(db, brainstorm_id)
    return GapDetectionResponse(
        gaps=[GapItem(**g) for g in gaps],
        total=len(gaps),
    )


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
        topic.name = sanitize_topic_name(data.name).lower().replace(" ", "-")
    if data.description is not None:
        topic.description = sanitize_topic_description(data.description)
    if data.position_x is not None:
        topic.position_x = data.position_x
    if data.position_y is not None:
        topic.position_y = data.position_y
    if data.outline is not None:
        topic.outline = [{"title": s.title} for s in data.outline]
    db.commit()
    invalidate_map_cache(brainstorm_id)
    db.refresh(topic)
    publish_brainstorm_event("topic_updated", brainstorm_id, {"topic_id": str(topic.id)})
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

    map_service.delete_topic(db, brainstorm_id, topic)

    publish_brainstorm_event("topic_deleted", brainstorm_id, {"topic_id": str(topic_id)})
    return None


@router.post("/{brainstorm_id}/topics", response_model=TopicResponse, status_code=201)
def create_topic_manual(
    brainstorm_id: uuid.UUID,
    data: TopicCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new topic on the canvas.

    When auto_generate=True (default), the topic is enriched with
    AI-generated library content and connected to existing topics.

    When auto_generate=False, a blank topic is created with only
    the name and optional outline — no AI calls are made.
    """
    brainstorm = brainstorm_service.get_brainstorm(db, brainstorm_id, user_id=current_user.id)
    if not brainstorm:
        raise HTTPException(status_code=404, detail="Brainstorm not found")

    # Sanitize inputs
    clean_name = sanitize_topic_name(data.name)
    if not clean_name:
        raise HTTPException(status_code=400, detail="Topic name is required")
    clean_desc = sanitize_topic_description(data.description or "")

    # Check for duplicate name
    existing = topic_service.get_topic_by_name(db, brainstorm_id, clean_name, is_proposition=False)
    if existing:
        raise HTTPException(status_code=409, detail="A topic with this name already exists")

    topic_name = clean_name.lower().replace(" ", "-")

    # Build outline list from request
    outline_data = None
    if data.outline is not None:
        outline_data = [
            {"title": s.title} for s in data.outline
        ]

    topic = topic_service.create_topic(
        db, brainstorm_id,
        name=topic_name,
        description=clean_desc,
        is_proposition=False,
        confidence=0.5,
        outline=outline_data,
    )

    if data.auto_generate:
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

        # Generate enriched library content via LLM
        try:
            conv_text = map_service.get_conversation_text(db, brainstorm_id)
            enriched = generate_library_content(
                topic_name=topic_name,
                conversation_text=conv_text if conv_text.strip() else topic_name,
            )
            taxonomy = generate_topic_taxonomy(
                topic_name=topic_name,
                library_content=enriched,
                conversation_text=conv_text,
            )
            if taxonomy:
                topic.taxonomy = taxonomy
                from app.services.topic_research_service import taxonomy_to_markdown
                taxonomy_md = taxonomy_to_markdown(taxonomy)
                if taxonomy_md:
                    enriched += "\n\n" + taxonomy_md

            file_name = f"{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.md"
            entry = create_library_entry(
                db, brainstorm_id,
                topic_id=topic.id,
                folder_name=topic_name,
                file_name=file_name,
                content=enriched,
                source_type="create",
            )
            topic.library_path = entry.file_path
            db.commit()
            invalidate_map_cache(brainstorm_id)
            db.refresh(topic)
        except Exception:
            pass  # Library entry is best-effort

        # Refresh suggestions
        rebuild_map_suggestions(db, brainstorm_id)

    publish_brainstorm_event("topic_created", brainstorm_id, {"topic_id": str(topic.id)})
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

    # Generate structured library content via LLM
    conv_text = map_service.get_conversation_text(db, brainstorm_id)
    enriched_content = generate_library_content(
        topic_name=topic.name,
        conversation_text=conv_text,
    )

    # Append taxonomy sections (parent/child/related)
    taxonomy = generate_topic_taxonomy(
        topic_name=topic.name,
        library_content=enriched_content,
        conversation_text=conv_text,
    )
    if taxonomy:
        topic.taxonomy = taxonomy
        from app.services.topic_research_service import taxonomy_to_markdown
        taxonomy_md = taxonomy_to_markdown(taxonomy)
        if taxonomy_md:
            enriched_content += "\n\n" + taxonomy_md

    file_name = f"{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.md"
    entry = create_library_entry(
        db, brainstorm_id,
        topic_id=topic.id,
        folder_name=topic.name,
        file_name=file_name,
        content=enriched_content,
        source_type="explore",
    )
    topic.library_path = entry.file_path
    topic.confidence = max(topic.confidence or 0.0, 0.7)
    db.commit()
    invalidate_map_cache(brainstorm_id)
    db.refresh(topic)

    # Rebuild suggestions
    rebuild_map_suggestions(db, brainstorm_id)
    return map_service.build_map_response(db, brainstorm_id)


# ─── Topic Content Generation (streaming) ─────────────────────


def _persist_generated_content(
    db: Session,
    brainstorm_id: uuid.UUID,
    topic_id: uuid.UUID,
    topic_name: str,
    full_response: str,
) -> dict:
    """Persist generated content to DB. Called via run_in_db from async context."""
    # Parse summary: first line starting with "> " is the summary
    lines = full_response.split("\n")
    summary = ""
    if lines and lines[0].startswith("> "):
        summary = lines[0][2:].strip()

    # Reload topic in the fresh session — must exist before we can create
    # a library entry that references it (FK constraint).
    topic = topic_service.get_topic(db, topic_id)
    if topic is None:
        raise RuntimeError(
            f"Topic {topic_id} not found in database — it may have been "
            "deleted between content generation and persistence."
        )

    if summary:
        topic.description = summary
    topic.outline = None
    topic.confidence = max(topic.confidence or 0.0, 0.8)

    # Create library entry
    folder_name = topic_name
    file_name = f"{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.md"
    entry = create_library_entry(
        db, brainstorm_id,
        topic_id=topic_id,
        folder_name=folder_name,
        file_name=file_name,
        content=full_response.strip(),
        source_type="generate",
    )
    topic.library_path = entry.file_path

    db.commit()
    invalidate_map_cache(brainstorm_id)

    # Rebuild suggestions
    rebuild_map_suggestions(db, brainstorm_id, commit=True)

    # Publish WebSocket event
    publish_brainstorm_event(
        "topic_generated",
        brainstorm_id,
        {"topic_id": str(topic_id), "library_entry_id": str(entry.id)},
    )

    return {"topic_id": str(topic_id), "summary": summary}


@router.post("/{brainstorm_id}/topics/{topic_id}/generate")
def generate_topic_content(
    brainstorm_id: uuid.UUID,
    topic_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Generate content for a topic using Wikipedia.

    Fetches the topic's Wikipedia article and streams the structured
    markdown content via Server-Sent Events, paragraph by paragraph.

    On completion, the summary is saved to topic.description, a
    LibraryEntry is created, and the topic's outline is cleared.
    """
    brainstorm = brainstorm_service.get_brainstorm(db, brainstorm_id, user_id=current_user.id)
    if not brainstorm:
        raise HTTPException(status_code=404, detail="Brainstorm not found")

    topic = topic_service.get_topic(db, topic_id)
    if not topic or topic.brainstorm_id != brainstorm_id:
        raise HTTPException(status_code=404, detail="Topic not found")

    display_name = topic.name.replace("-", " ").title()

    async def event_stream():
        from app.services.wikipedia_service import get_page, page_to_markdown, search

        # Resolve topic to Wikipedia article
        try:
            page = await get_page(display_name)
            if page is None:
                # Try search
                results = await search(display_name, limit=1)
                if results:
                    page = await get_page(results[0].title)
        except Exception as e:
            logger.error("Wikipedia fetch error for topic %s: %s", topic_id, e)
            yield f"data: {json.dumps({'error': str(e)})}\n\n"
            return

        if page is None:
            yield f"data: {json.dumps({'done': True, 'error': 'No Wikipedia article found for this topic'})}\n\n"
            return

        # Generate markdown content
        full_response = page_to_markdown(page)

        # Stream paragraphs with a small delay for visual feedback
        paragraphs = full_response.split("\n\n")
        for para in paragraphs:
            if para.strip():
                token = para + "\n\n"
                full_response += ""  # already have the full content
                yield f"data: {json.dumps({'token': token})}\n\n"
                await asyncio.sleep(0.05)  # small delay for smooth streaming

        # Persist via thread-pool executor
        try:
            result = await run_in_db(
                lambda db_session: _persist_generated_content(
                    db_session, brainstorm_id, topic_id, topic.name, full_response,
                )
            )
            yield f"data: {json.dumps({'done': True, **result})}\n\n"
        except Exception as e:
            logger.error("Failed to persist generated content for topic %s: %s", topic_id, e)
            yield f"data: {json.dumps({'error': f'Failed to save content: {e}'})}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ─── Edge CRUD ─────────────────────────────────────────────────


# ─── Edge Connection Exploration ──────────────────────────────

# Prompt is defined in app.tasks.research_tasks (shared with Celery task)
from app.tasks.research_tasks import (
    process_connection_exploration,
    process_connection_exploration_sync,
    CONNECTION_PROMPT,
)


class ExploreConnectionRequest(BaseModel):
    source_topic_id: uuid.UUID
    target_topic_id: uuid.UUID
    position_x: float = 0.0
    position_y: float = 0.0


@router.post("/{brainstorm_id}/explore-connection", status_code=202)
def explore_connection(
    brainstorm_id: uuid.UUID,
    data: ExploreConnectionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a topic explaining how two existing topics are connected.

    Dispatches the LLM call and topic creation to a Celery task and
    returns 202 Accepted immediately. Results are published via
    WebSocket (topic_generated event) when ready.

    Falls back to synchronous execution if Celery/Redis is unavailable.
    """
    brainstorm = brainstorm_service.get_brainstorm(db, brainstorm_id, user_id=current_user.id)
    if not brainstorm:
        raise HTTPException(status_code=404, detail="Brainstorm not found")

    source = topic_service.get_topic(db, data.source_topic_id)
    target = topic_service.get_topic(db, data.target_topic_id)
    if not source or source.brainstorm_id != brainstorm_id:
        raise HTTPException(status_code=404, detail="Source topic not found")
    if not target or target.brainstorm_id != brainstorm_id:
        raise HTTPException(status_code=404, detail="Target topic not found")

    # Check for duplicate connection topic (fast DB check, no LLM needed)
    connection_name = f"{source.name}-{target.name}-connection"
    existing = topic_service.get_topic_by_name(db, brainstorm_id, connection_name, is_proposition=False)
    if existing:
        raise HTTPException(status_code=409, detail="A connection topic between these two already exists")

    # Dispatch to Celery — returns immediately, results via WebSocket
    try:
        process_connection_exploration.delay(
            str(brainstorm_id),
            str(data.source_topic_id),
            str(data.target_topic_id),
            data.position_x,
            data.position_y,
        )
        logger.info(
            "connection_exploration dispatched | brainstorm=%s source=%s target=%s",
            brainstorm_id, source.name, target.name,
        )
    except Exception as e:
        logger.warning("Celery dispatch failed, running connection exploration synchronously: %s", e)
        try:
            result = process_connection_exploration_sync(
                str(brainstorm_id),
                str(data.source_topic_id),
                str(data.target_topic_id),
                data.position_x,
                data.position_y,
            )
            if result.get("status") == "error":
                raise HTTPException(
                    status_code=500,
                    detail=result.get("error", "Connection exploration failed"),
                )
        except HTTPException:
            raise
        except Exception as sync_e:
            logger.error("Synchronous connection exploration also failed: %s", sync_e)
            raise HTTPException(
                status_code=500,
                detail=f"Failed to generate connection content: {sync_e}",
            )

    return JSONResponse(
        status_code=202,
        content={
            "status": "processing",
            "source_topic_id": str(data.source_topic_id),
            "target_topic_id": str(data.target_topic_id),
        },
    )


# ─── Edge CRUD ─────────────────────────────────────────────────

@router.post("/{brainstorm_id}/edges", response_model=TopicEdgeResponse, status_code=201)
def create_edge_manual(
    brainstorm_id: uuid.UUID,
    data: EdgeCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    brainstorm = brainstorm_service.get_brainstorm(db, brainstorm_id, user_id=current_user.id)
    if not brainstorm:
        raise HTTPException(status_code=404, detail="Brainstorm not found")

    source = topic_service.get_topic(db, data.source_topic_id)
    target = topic_service.get_topic(db, data.target_topic_id)
    if not source or source.brainstorm_id != brainstorm_id:
        raise HTTPException(status_code=404, detail="Source topic not found")
    if not target or target.brainstorm_id != brainstorm_id:
        raise HTTPException(status_code=404, detail="Target topic not found")

    existing = topic_service.get_edge_between(
        db, brainstorm_id,
        source_topic_id=data.source_topic_id,
        target_topic_id=data.target_topic_id,
    )
    if existing:
        raise HTTPException(status_code=409, detail="Edge already exists")

    edge = topic_service.create_edge(
        db, brainstorm_id,
        source_topic_id=data.source_topic_id,
        target_topic_id=data.target_topic_id,
        relationship=data.relationship,
        weight=data.weight,
    )
    invalidate_map_cache(brainstorm_id)
    publish_brainstorm_event("edge_created", brainstorm_id, {
        "edge_id": str(edge.id),
        "source_topic_id": str(data.source_topic_id),
        "target_topic_id": str(data.target_topic_id),
    })
    return TopicEdgeResponse(
        id=edge.id,
        source_topic_id=edge.source_topic_id,
        target_topic_id=edge.target_topic_id,
        relationship=edge.relationship,
        weight=edge.weight,
        source_name=source.name,
        target_name=target.name,
    )


@router.delete("/{brainstorm_id}/edges/{edge_id}", status_code=204)
def delete_edge_manual(
    brainstorm_id: uuid.UUID,
    edge_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    edge = map_service.delete_edge(db, brainstorm_id, edge_id)
    if not edge:
        raise HTTPException(status_code=404, detail="Edge not found")
    publish_brainstorm_event("edge_deleted", brainstorm_id, {"edge_id": str(edge_id)})
    return None


# ─── Topic Comments ──────────────────────────────────────────

class CommentRequest(BaseModel):
    content: str = Field(..., min_length=1, max_length=5000)


class CommentResponse(BaseModel):
    id: uuid.UUID
    topic_id: uuid.UUID
    content: str
    created_at: datetime


@router.get("/{brainstorm_id}/topics/{topic_id}/comments", response_model=list[CommentResponse])
def get_topic_comments(
    brainstorm_id: uuid.UUID,
    topic_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get all comments on a topic, ordered by creation time."""
    brainstorm = brainstorm_service.get_brainstorm(db, brainstorm_id, user_id=current_user.id)
    if not brainstorm:
        raise HTTPException(status_code=404, detail="Brainstorm not found")

    topic = topic_service.get_topic(db, topic_id)
    if not topic or topic.brainstorm_id != brainstorm_id:
        raise HTTPException(status_code=404, detail="Topic not found")

    comments = map_service.get_topic_comments(db, topic_id)

    return [
        CommentResponse(
            id=c.id,
            topic_id=topic_id,
            content=c.content,
            created_at=c.created_at,
        )
        for c in comments
    ]


@router.post("/{brainstorm_id}/topics/{topic_id}/comments", response_model=CommentResponse, status_code=201)
def add_topic_comment(
    brainstorm_id: uuid.UUID,
    topic_id: uuid.UUID,
    data: CommentRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Add a comment to a topic."""
    brainstorm = brainstorm_service.get_brainstorm(db, brainstorm_id, user_id=current_user.id)
    if not brainstorm:
        raise HTTPException(status_code=404, detail="Brainstorm not found")

    topic = topic_service.get_topic(db, topic_id)
    if not topic or topic.brainstorm_id != brainstorm_id:
        raise HTTPException(status_code=404, detail="Topic not found")

    msg = Message(
        id=uuid.uuid4(),
        brainstorm_id=brainstorm_id,
        topic_id=topic_id,
        role="user",
        content=data.content,
    )
    db.add(msg)
    db.commit()
    db.refresh(msg)

    return CommentResponse(
        id=msg.id,
        topic_id=topic_id,
        content=msg.content,
        created_at=msg.created_at,
    )
