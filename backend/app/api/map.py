from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
import uuid
import json
from datetime import datetime, timezone

from app.database import get_db, SessionLocal
from app.schemas.topic import (
    MapDataResponse, TopicResponse, TopicEdgeResponse, SuggestionResponse,
    TopicUpdateRequest, TopicCreateRequest, EdgeCreateRequest,
)
from app.services import topic_service, brainstorm_service, message_service
from app.services.map_suggestion_service import rebuild_map_suggestions
from app.services.library_service import create_library_entry
from app.services.topic_enrichment_service import (
    generate_library_content,
    generate_topic_taxonomy,
)
from app.services.ai_service import (
    stream_chat_with_model,
    chat_with_model_sync,
    resolve_credentials,
)
from app.api.auth import get_current_user
from app.models.user import User
from app.models.topic import Topic
from app.models.topic_edge import TopicEdge
from app.sanitize import sanitize_topic_name, sanitize_topic_description
from pydantic import BaseModel
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/map", tags=["map"])


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


@router.get("/{brainstorm_id}", response_model=MapDataResponse)
def get_map(
    brainstorm_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get the full knowledge map including topics, edges, and suggestions."""
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
            conv_text = _get_brainstorm_conversation_text(db, brainstorm_id)
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
                from app.tasks.classification_tasks import _taxonomy_to_markdown
                taxonomy_md = _taxonomy_to_markdown(taxonomy)
                if taxonomy_md:
                    enriched += "\n\n" + taxonomy_md

            file_name = f"{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.md"
            entry = create_library_entry(
                db, brainstorm_id,
                topic_id=topic.id,
                folder_name=topic_name,
                file_name=file_name,
                content=enriched,
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

    # Generate structured library content via LLM
    conv_text = _get_brainstorm_conversation_text(db, brainstorm_id)
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
        from app.tasks.classification_tasks import _taxonomy_to_markdown
        taxonomy_md = _taxonomy_to_markdown(taxonomy)
        if taxonomy_md:
            enriched_content += "\n\n" + taxonomy_md

    file_name = f"{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.md"
    entry = create_library_entry(
        db, brainstorm_id,
        topic_id=topic.id,
        folder_name=topic.name,
        file_name=file_name,
        content=enriched_content,
    )
    topic.library_path = entry.file_path
    topic.confidence = max(topic.confidence or 0.0, 0.7)
    db.commit()
    db.refresh(topic)

    # Rebuild suggestions
    rebuild_map_suggestions(db, brainstorm_id)
    return _build_map_response(db, brainstorm_id)


# ─── Topic Content Generation (streaming) ─────────────────────

GENERATE_OUTLINE_PROMPT = """You are a knowledgeable researcher. Write comprehensive content about "{topic_name}".

Start with a single-line summary prefixed with "> ".

Then cover the following sections using ## headings:

{sections}

For each section, write well-structured paragraphs using markdown formatting
(lists, bold, italics as appropriate). Be thorough, accurate, and engaging.

Do not include any preamble or meta-commentary — start directly with the summary line."""


GENERATE_FULL_PROMPT = """You are a knowledgeable researcher. Write comprehensive content about "{topic_name}".

Structure your response as follows:

> A single-line summary capturing the essence of {topic_name}.

## Overview
3-4 paragraphs: what it is, how it works, key characteristics, history, why it matters. Minimum 150 words.

## Key Concepts
- **Concept Name**: 2-3 sentence explanation
- **Concept Name**: 2-3 sentence explanation
(4-6 entries)

## Use Cases
- **Use Case**: 2-3 sentence description
- **Use Case**: 2-3 sentence description
(2-4 entries)

## Related Topics
- topic-name-slug - How it relates to or compares with {topic_name}
- another-topic-slug - How this topic complements {topic_name}
(2-3 entries, use lowercase-hyphenated names)

Use markdown formatting throughout. Be thorough, accurate, and engaging.
Do not include any preamble or meta-commentary — start directly with the summary line."""


@router.post("/{brainstorm_id}/topics/{topic_id}/generate")
def generate_topic_content(
    brainstorm_id: uuid.UUID,
    topic_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Generate AI content for a topic.

    Two modes, chosen automatically:

    1. **With outline** — if the topic has stored outline sections, content
       is generated to match those section titles exactly.

    2. **Full research** — if no outline exists, a comprehensive research
       document is generated with overview, key concepts, use cases, and
       related topics.

    The response is streamed via Server-Sent Events. On completion, the
    summary is saved to topic.description, a LibraryEntry is created, and
    the topic's outline is cleared (if it existed).
    """
    brainstorm = brainstorm_service.get_brainstorm(db, brainstorm_id, user_id=current_user.id)
    if not brainstorm:
        raise HTTPException(status_code=404, detail="Brainstorm not found")

    topic = topic_service.get_topic(db, topic_id)
    if not topic or topic.brainstorm_id != brainstorm_id:
        raise HTTPException(status_code=404, detail="Topic not found")

    display_name = topic.name.replace("-", " ").title()

    # Choose prompt based on whether the topic has an outline
    has_outline = topic.outline and isinstance(topic.outline, list) and len(topic.outline) > 0

    if has_outline:
        section_titles = [
            s.get("title", "").strip()
            for s in topic.outline
            if isinstance(s, dict) and s.get("title", "").strip()
        ]
        if not section_titles:
            has_outline = False

    if has_outline:
        sections_text = "\n".join(f"## {t}" for t in section_titles)
        prompt = GENERATE_OUTLINE_PROMPT.format(topic_name=display_name, sections=sections_text)
    else:
        prompt = GENERATE_FULL_PROMPT.format(topic_name=display_name)

    model = brainstorm.model
    api_key, base_url = resolve_credentials(db, model)

    async def event_stream():
        full_response = ""
        try:
            async for token in stream_chat_with_model(
                [{"role": "user", "content": prompt}],
                model,
                api_key=api_key,
                base_url=base_url,
            ):
                full_response += token
                yield f"data: {json.dumps({'token': token})}\n\n"
        except Exception as e:
            logger.error("Generate stream error for topic %s: %s", topic_id, e)
            yield f"data: {json.dumps({'error': str(e)})}\n\n"
            return

        # Persist results in a fresh session
        persist_db = SessionLocal()
        try:
            if not full_response.strip():
                yield f"data: {json.dumps({'done': True, 'error': 'Empty response from model'})}\n\n"
                return

            # Parse summary: first line starting with "> " is the summary
            lines = full_response.split("\n")
            summary = ""
            if lines and lines[0].startswith("> "):
                summary = lines[0][2:].strip()

            # Reload topic in the persist session
            persist_topic = persist_db.query(Topic).filter(Topic.id == topic_id).first()
            if persist_topic:
                if summary:
                    persist_topic.description = summary
                persist_topic.outline = None
                persist_topic.confidence = max(persist_topic.confidence or 0.0, 0.8)

            # Create library entry
            folder_name = topic.name
            file_name = f"{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.md"
            entry = create_library_entry(
                persist_db, brainstorm_id,
                topic_id=topic_id,
                folder_name=folder_name,
                file_name=file_name,
                content=full_response.strip(),
            )
            if persist_topic:
                persist_topic.library_path = entry.file_path

            persist_db.commit()

            # Rebuild suggestions so the card shows proposition pills
            from app.services.map_suggestion_service import rebuild_map_suggestions
            rebuild_map_suggestions(persist_db, brainstorm_id, commit=True)

            # Publish WebSocket event so frontend reloads library
            from app.services.realtime_service import publish_brainstorm_event
            publish_brainstorm_event(
                "topic_generated",
                brainstorm_id,
                {
                    "topic_id": str(topic_id),
                    "library_entry_id": str(entry.id),
                },
            )

            yield f"data: {json.dumps({'done': True, 'topic_id': str(topic_id), 'summary': summary})}\n\n"

        except Exception as e:
            logger.error("Failed to persist generated content for topic %s: %s", topic_id, e)
            yield f"data: {json.dumps({'error': f'Failed to save content: {e}'})}\n\n"
        finally:
            persist_db.close()

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


class ExploreConnectionRequest(BaseModel):
    source_topic_id: uuid.UUID
    target_topic_id: uuid.UUID
    position_x: float = 0.0
    position_y: float = 0.0


@router.post("/{brainstorm_id}/explore-connection", response_model=TopicResponse, status_code=201)
def explore_connection(
    brainstorm_id: uuid.UUID,
    data: ExploreConnectionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a topic explaining how two existing topics are connected.

    Creates a new topic card positioned between the two topics,
    generates AI content explaining their relationship, and
    links the new topic to both source and target via edges.
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

    source_display = source.name.replace("-", " ").title()
    target_display = target.name.replace("-", " ").title()
    connection_name = f"{source.name}-{target.name}-connection"

    # Check for duplicate connection topic
    existing = topic_service.get_topic_by_name(db, brainstorm_id, connection_name, is_proposition=False)
    if existing:
        raise HTTPException(status_code=409, detail="A connection topic between these two already exists")

    # Build prompt and generate content synchronously
    prompt = CONNECTION_PROMPT.format(topic_a=source_display, topic_b=target_display)
    model = brainstorm.model
    api_key, base_url = resolve_credentials(db, model)

    try:
        raw = chat_with_model_sync([{"role": "user", "content": prompt}], model=model, api_key=api_key, base_url=base_url)
    except Exception as e:
        logger.error("Connection generation failed: %s", e)
        raise HTTPException(status_code=500, detail=f"Failed to generate connection content: {e}")

    # Parse summary (first line starting with "> ")
    lines = raw.split("\n")
    summary = ""
    if lines and lines[0].startswith("> "):
        summary = lines[0][2:].strip()

    # Create the connection topic
    connection = topic_service.create_topic(
        db, brainstorm_id,
        name=connection_name,
        description=summary or f"Connection between {source_display} and {target_display}",
        is_proposition=False,
        confidence=0.7,
        outline=None,
    )

    # Position between the two topics
    connection.position_x = data.position_x
    connection.position_y = data.position_y

    # Create library entry
    file_name = f"{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.md"
    entry = create_library_entry(
        db, brainstorm_id,
        topic_id=connection.id,
        folder_name=connection_name,
        file_name=file_name,
        content=raw.strip(),
    )
    connection.library_path = entry.file_path

    # Create edges from connection to both source and target (fixed, non-removable)
    topic_service.create_edge(
        db, brainstorm_id,
        source_topic_id=connection.id,
        target_topic_id=source.id,
        relationship="connection_link",
        weight=0.5,
    )
    topic_service.create_edge(
        db, brainstorm_id,
        source_topic_id=connection.id,
        target_topic_id=target.id,
        relationship="connection_link",
        weight=0.5,
    )

    # Remove the original direct edge between source and target —
    # they're now linked through the connection card instead.
    db.query(TopicEdge).filter(
        TopicEdge.brainstorm_id == brainstorm_id,
        ((TopicEdge.source_topic_id == source.id) & (TopicEdge.target_topic_id == target.id))
        | ((TopicEdge.source_topic_id == target.id) & (TopicEdge.target_topic_id == source.id)),
    ).delete(synchronize_session=False)

    db.commit()
    db.refresh(connection)

    # Rebuild suggestions
    rebuild_map_suggestions(db, brainstorm_id)

    # Notify frontend
    from app.services.realtime_service import publish_brainstorm_event
    publish_brainstorm_event(
        "topic_generated",
        brainstorm_id,
        {"topic_id": str(connection.id), "library_entry_id": str(entry.id)},
    )

    return connection


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

    existing = db.query(TopicEdge).filter(
        TopicEdge.brainstorm_id == brainstorm_id,
        TopicEdge.source_topic_id == data.source_topic_id,
        TopicEdge.target_topic_id == data.target_topic_id,
    ).first()
    if existing:
        raise HTTPException(status_code=409, detail="Edge already exists")

    edge = topic_service.create_edge(
        db, brainstorm_id,
        source_topic_id=data.source_topic_id,
        target_topic_id=data.target_topic_id,
        relationship=data.relationship,
        weight=data.weight,
    )
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
    edge = db.query(TopicEdge).filter(
        TopicEdge.id == edge_id,
        TopicEdge.brainstorm_id == brainstorm_id,
    ).first()
    if not edge:
        raise HTTPException(status_code=404, detail="Edge not found")
    db.delete(edge)
    db.commit()
    return None


def _get_brainstorm_conversation_text(db: Session, brainstorm_id: uuid.UUID) -> str:
    """Build conversation text from stored messages."""
    messages, _ = message_service.get_messages(db, brainstorm_id, limit=200)
    parts = []
    for msg in messages:
        role_label = "User" if msg.role.value == "user" else "Assistant"
        parts.append(f"{role_label}: {msg.content}")
    return "\n\n".join(parts)
