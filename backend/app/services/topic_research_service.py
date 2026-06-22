"""
Topic research service — knowledge map generation from Wikipedia data.

Fetches structured knowledge from Wikipedia, builds a knowledge map
with topic cards, library entries, and proposition topics for the
parent/child/related taxonomy.
"""

import logging
import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.topic import Topic
from app.services.topic_service import (
    create_topic, create_edge, get_topic_by_name,
    normalize_topic_name, delete_propositions,
)
from app.services.library_service import create_library_entry
from app.services.brainstorm_service import get_brainstorm, update_brainstorm_title
from app.models.topic_edge import TopicEdge

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────
# Research Prompt — one call to rule them all
# ─────────────────────────────────────────────────────────────────────

@dataclass
class ResearchResult:
    """Parsed research output from the LLM."""
    summary: str = ""
    overview: str = ""
    key_concepts: List[dict] = field(default_factory=list)
    use_cases: List[dict] = field(default_factory=list)
    parent_topics: List[dict] = field(default_factory=list)
    child_topics: List[dict] = field(default_factory=list)
    related_topics: List[dict] = field(default_factory=list)


def _research_to_markdown(
    topic_name: str,
    result: ResearchResult,
    library_content: str = "",
    include_taxonomy: bool = True,
) -> str:
    """Convert a ResearchResult into structured markdown for the library entry.

    The library_content parameter can contain additional LLM-generated content
    to prepend. If empty, builds the entire document from ResearchResult.

    Taxonomy sections (parent/child/related topics) are only included when
    include_taxonomy=True. By default they are omitted because
    build_knowledge_map() creates proposition topics directly on the canvas,
    making markdown-level taxonomy redundant.
    """
    display = topic_name.replace("-", " ").title()
    lines = []

    if library_content.strip():
        lines.append(library_content.strip())
    else:
        # Build from ResearchResult fields
        lines.append(f"# {display}")
        lines.append("")
        if result.summary:
            lines.append(f"> {result.summary}")
            lines.append("")
        if result.overview:
            lines.append("## Overview")
            lines.append("")
            lines.append(result.overview)
            lines.append("")

        if result.key_concepts:
            lines.append("## Key Concepts")
            lines.append("")
            for kc in result.key_concepts:
                name = kc.get("name", "").strip()
                desc = kc.get("description", "").strip()
                lines.append(f"- **{name}**: {desc}")
            lines.append("")

        if result.use_cases:
            lines.append("## Use Cases")
            lines.append("")
            for uc in result.use_cases:
                name = uc.get("name", "").strip()
                desc = uc.get("description", "").strip()
                lines.append(f"- **{name}**: {desc}")
            lines.append("")

    # Taxonomy sections — only included when requested (e.g., from the chat pipeline
    # where proposition topics aren't created separately)
    if include_taxonomy:
        for key, heading in [
            ("parent_topics", "Parent Topics"),
            ("child_topics", "Child Topics"),
            ("related_topics", "Related Topics"),
        ]:
            items = getattr(result, key, [])
            if not items:
                continue
            lines.append(f"## {heading}")
            lines.append("")
            for item in items:
                name = item.get("name", "unknown")
                desc = item.get("description", "")
                lines.append(f"- {name} - {desc}")
            lines.append("")

    return "\n".join(lines)


def taxonomy_to_markdown(taxonomy: dict) -> str:
    """Convert a taxonomy dict to markdown sections for library entries.

    Args:
        taxonomy: Dict with parent_topics, child_topics, related_topics keys,
                  each containing [{"name": str, "description": str}, ...]

    Returns:
        Markdown string with ## Parent Topics, ## Child Topics, ## Related Topics.
    """
    sections = []
    for key, heading in [
        ("parent_topics", "Parent Topics"),
        ("child_topics", "Child Topics"),
        ("related_topics", "Related Topics"),
    ]:
        items = taxonomy.get(key, [])
        if items:
            lines = [f"## {heading}", ""]
            for item in items:
                name = item.get("name", "unknown")
                desc = item.get("description", "")
                lines.append(f"- {name} - {desc}")
            sections.append("\n".join(lines))
    return "\n\n".join(sections)


def research_topic(
    topic_name: str,
    model: Optional[str] = None,
) -> Optional[ResearchResult]:
    """Research a topic using Wikipedia.

    Resolves the topic name to a Wikipedia article, fetches structured
    page data, and transforms it into a ResearchResult with overview,
    key concepts, use cases, and parent/child/related taxonomy.

    Returns None if Wikipedia has no article for this topic.
    """
    from app.services.wikipedia_service import resolve_page_sync, page_to_research_result

    t0 = time.perf_counter()
    display = topic_name.replace("-", " ").title()

    logger.debug("research_topic start (wikipedia) | topic=%s", topic_name)

    try:
        page = resolve_page_sync(display)
        elapsed = time.perf_counter() - t0

        if page is None:
            logger.warning(
                "research_topic no_article | topic=%s elapsed=%.2fs",
                topic_name, elapsed,
            )
            return None

        result = page_to_research_result(page)

        logger.debug(
            "research_topic done (wikipedia) | topic=%s elapsed=%.2fs "
            "concepts=%d use_cases=%d parents=%d children=%d related=%d "
            "pageid=%d",
            topic_name, elapsed,
            len(result.key_concepts), len(result.use_cases),
            len(result.parent_topics), len(result.child_topics),
            len(result.related_topics), page.pageid,
        )
        return result

    except Exception as e:
        elapsed = time.perf_counter() - t0
        logger.error("research_topic error | topic=%s elapsed=%.2fs error=%s", topic_name, elapsed, e)
        return None


def build_knowledge_map(
    db: Session,
    brainstorm_id: UUID,
    topic_name: str,
    result: ResearchResult,
    commit: bool = True,
    model: Optional[str] = None,
) -> Topic:
    """Build the knowledge map from a ResearchResult.

    Creates:
      - Primary topic with structured library entry
      - Proposition topics for parent/child/related taxonomy
      - Suggestion edges from primary topic to each proposition
      - Updates brainstorm title if still default

    Returns the primary topic.
    """
    existing_topics = db.query(Topic).filter(
        Topic.brainstorm_id == brainstorm_id, Topic.is_proposition == False
    ).all()
    existing_names = {normalize_topic_name(t.name) for t in existing_topics}

    # Build markdown from ResearchResult
    md_content = _research_to_markdown(topic_name, result)

    # Create or update the primary topic
    normalized = normalize_topic_name(topic_name)
    slug = normalized.replace(" ", "-") if normalized else topic_name.lower().replace(" ", "-")
    primary = get_topic_by_name(db, brainstorm_id, normalized, is_proposition=False)

    if primary:
        primary.confidence = max(primary.confidence or 0.0, 0.85)
        # Update library entry if one exists
    else:
        primary = create_topic(
            db=db,
            brainstorm_id=brainstorm_id,
            name=slug,
            description=result.summary or "Researched topic.",
            is_proposition=False,
            confidence=0.85,
            commit=False,
        )

    # Create library entry
    file_name = f"{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.md"
    entry = create_library_entry(
        db=db,
        brainstorm_id=brainstorm_id,
        topic_id=primary.id,
        folder_name=slug,
        file_name=file_name,
        content=md_content,
        commit=False,
        source_type="research",
        source_model=model if model else None,
    )
    primary.library_path = entry.file_path

    # Store taxonomy directly on the topic (no markdown roundtrip)
    primary.taxonomy = {
        "parent_topics": result.parent_topics,
        "child_topics": result.child_topics,
        "related_topics": result.related_topics,
    }

    # Clear old propositions and suggestion edges for this topic
    db.query(TopicEdge).filter(
        TopicEdge.brainstorm_id == brainstorm_id,
        TopicEdge.relationship.in_([
            "suggestion", "suggestion:parent", "suggestion:child", "suggestion:related",
        ]),
        TopicEdge.source_topic_id == primary.id,
    ).delete(synchronize_session=False)

    old_props = db.query(Topic).filter(
        Topic.brainstorm_id == brainstorm_id,
        Topic.is_proposition == True,
    ).all()
    for prop in old_props:
        # Only delete propositions that were suggestions from this topic
        edge = db.query(TopicEdge).filter(
            TopicEdge.brainstorm_id == brainstorm_id,
            TopicEdge.source_topic_id == primary.id,
            TopicEdge.target_topic_id == prop.id,
        ).first()
        if not edge:
            continue
        db.delete(prop)

    # Create proposition topics from taxonomy
    all_names = existing_names | {normalized}
    kind_map = [
        ("parent_topics", "suggestion:parent", "Parent", 0.35),
        ("child_topics", "suggestion:child", "Child", 0.35),
        ("related_topics", "suggestion:related", "Related", 0.35),
    ]

    created_count = 0
    for attr, edge_rel, kind_label, weight in kind_map:
        items = getattr(result, attr, [])
        for item in items[:3]:
            candidate_slug = item.get("name", "").strip().lower().replace(" ", "-")
            candidate_normalized = normalize_topic_name(candidate_slug)
            if not candidate_normalized or candidate_normalized in all_names:
                continue

            prop = create_topic(
                db=db,
                brainstorm_id=brainstorm_id,
                name=candidate_slug,
                description=f"[{kind_label}] {item.get('description', '')}",
                is_proposition=True,
                confidence=weight + 0.05,
                commit=False,
            )
            all_names.add(candidate_normalized)
            create_edge(
                db=db,
                brainstorm_id=brainstorm_id,
                source_topic_id=primary.id,
                target_topic_id=prop.id,
                relationship=edge_rel,
                weight=weight,
                commit=False,
            )
            created_count += 1

    # Update brainstorm title if still default
    brainstorm = get_brainstorm(db, brainstorm_id)
    if brainstorm and brainstorm.title == "New Brainstorm":
        update_brainstorm_title(db, brainstorm_id, display.replace("-", " ").title())

    if commit:
        db.commit()
        db.refresh(primary)

    logger.info(
        "build_knowledge_map done | topic=%s propositions=%d",
        topic_name, created_count,
    )
    return primary
