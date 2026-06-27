"""
Enrichment service — single source of truth for topic enrichment + library persistence.

Consolidates the duplicated "enrich + create library entry + rebuild suggestions"
pattern that previously existed in 5 separate locations across map.py,
research_tasks.py, and topic_research_service.py.

Two functions:
  1. enrich_from_wikipedia()  — auto-generate content + taxonomy from Wikipedia
  2. create_topic_library_entry()  — persist already-generated content to a library entry
"""

import logging
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from app.services.library_service import create_library_entry
from app.services.map_suggestion_service import rebuild_map_suggestions
from app.services.realtime_service import invalidate_map_cache

logger = logging.getLogger(__name__)


def enrich_from_wikipedia(
    db: Session,
    brainstorm_id: str,
    topic,                      # Topic ORM instance (must have .id, .name, .library_path)
    topic_name: str,            # display name for Wikipedia lookup
    conversation_text: str = "",
    source_type: str = "create",
) -> str:
    """Generate library content + taxonomy from Wikipedia, persist as library entry.

    This replaces the 15-line block that was duplicated in map.py's
    create_topic_manual() and explore_topic().

    Args:
        db: Database session.
        brainstorm_id: Brainstorm UUID.
        topic: The Topic ORM object to enrich (mutated in-place).
        topic_name: Display name used for Wikipedia lookup.
        conversation_text: Conversation context for content generation.
        source_type: "create" or "explore" — passed to library entry.

    Returns:
        The generated markdown content string.
    """
    from app.services.topic_research_service import (
        generate_library_content,
        generate_topic_taxonomy,
    )
    from app.formatters import taxonomy_to_markdown

    # Step 1: Generate markdown content from Wikipedia
    enriched = generate_library_content(
        topic_name=topic_name,
        conversation_text=conversation_text if conversation_text.strip() else topic_name,
    )

    # Step 2: Generate taxonomy (parent/child/related) from Wikipedia
    taxonomy = generate_topic_taxonomy(
        topic_name=topic_name,
        library_content=enriched,
        conversation_text=conversation_text,
    )
    if taxonomy:
        topic.taxonomy = taxonomy
        taxonomy_md = taxonomy_to_markdown(taxonomy)
        if taxonomy_md:
            enriched += "\n\n" + taxonomy_md

    # Step 3: Persist as library entry
    create_topic_library_entry(
        db=db,
        brainstorm_id=brainstorm_id,
        topic=topic,
        folder_name=topic_name,
        content=enriched,
        source_type=source_type,
    )

    return enriched


def create_topic_library_entry(
    db: Session,
    brainstorm_id: str,
    topic,                      # Topic ORM instance (must have .id, .library_path)
    folder_name: str,
    content: str,
    source_type: str = "generate",
    source_model: Optional[str] = None,
    commit: bool = True,
    publish_event: bool = False,
) -> None:
    """Create a library entry for a topic and update its metadata.

    Handles the shared boilerplate:
      - Create library entry via library_service
      - Set topic.library_path
      - Commit (optional — set commit=False for batch operations)
      - Invalidate map cache
      - Rebuild suggestions

    Args:
        db: Database session.
        brainstorm_id: Brainstorm UUID.
        topic: Topic ORM object (mutated: library_path is set).
        folder_name: Folder name for the library entry.
        content: Markdown content for the library entry.
        source_type: "generate", "research", "connection", "create", or "explore".
        source_model: Model used to generate content (optional).
        commit: If True, commits the transaction.
        publish_event: If True, publishes a topic_generated WebSocket event.
    """
    file_name = f"{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.md"

    entry = create_library_entry(
        db,
        brainstorm_id,
        topic_id=topic.id,
        folder_name=folder_name,
        file_name=file_name,
        content=content.strip(),
        source_type=source_type,
        source_model=source_model,
        commit=False,
    )
    topic.library_path = entry.file_path

    if commit:
        db.commit()
        invalidate_map_cache(brainstorm_id)
        db.refresh(topic)

    # Rebuild suggestions for the updated map
    rebuild_map_suggestions(db, brainstorm_id, commit=commit)

    if publish_event:
        from app.services.realtime_service import publish_brainstorm_event
        publish_brainstorm_event(
            "topic_generated",
            brainstorm_id,
            {"topic_id": str(topic.id), "library_entry_id": str(entry.id)},
        )

    logger.debug(
        "create_topic_library_entry done | topic=%s source=%s chars=%d",
        topic.name, source_type, len(content),
    )
    return entry
