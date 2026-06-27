"""
Topic research service — knowledge map generation from Wikipedia data.

Fetches structured knowledge from Wikipedia, builds a knowledge map
with topic cards, library entries, and proposition topics for the
parent/child/related taxonomy.
"""

import logging
import re
import time
from datetime import datetime, timezone
from typing import List, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.topic import Topic
from app.services.topic_service import (
    create_topic, create_edge, get_topic_by_name,
    normalize_topic_name, delete_propositions,
)
from app.services.enrichment_service import create_topic_library_entry
from app.services.brainstorm_service import get_brainstorm, update_brainstorm_title
from app.models.topic_edge import TopicEdge
from app.schemas.research import ResearchResult
from app.formatters import research_result_to_markdown, taxonomy_to_markdown

logger = logging.getLogger(__name__)


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
    display = topic_name.replace("-", " ").strip()

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
    md_content = research_result_to_markdown(topic_name, result)

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

    # Create library entry and store taxonomy
    create_topic_library_entry(
        db=db,
        brainstorm_id=brainstorm_id,
        topic=primary,
        folder_name=slug,
        content=md_content,
        source_type="research",
        source_model=model if model else None,
        commit=False,
    )
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


# ─────────────────────────────────────────────────────────────────────
# Wikipedia enrichment — library content + taxonomy generation
# ─────────────────────────────────────────────────────────────────────
# (Merged from topic_enrichment_service.py — Phase 2 cleanup)


def generate_library_content(
    topic_name: str,
    conversation_text: str,
    model: Optional[str] = None,
) -> str:
    """Generate a structured markdown library entry for a topic using Wikipedia.

    Resolves the topic name to a Wikipedia article and produces a document
    with Overview, Key Concepts, Use Cases, and Source sections.

    Falls back to a minimal entry if Wikipedia has no article.
    """
    from app.services.wikipedia_service import resolve_page_sync, page_to_markdown

    t0 = time.perf_counter()
    display_name = topic_name.replace("-", " ").strip()

    logger.debug("generate_library_content start (wikipedia) | topic=%s", topic_name)

    try:
        page = resolve_page_sync(display_name)
        elapsed = time.perf_counter() - t0

        if page is None:
            logger.debug(
                "generate_library_content no_article | topic=%s elapsed=%.2fs",
                topic_name, elapsed,
            )
            return (
                f"# {display_name}\n\n"
                f"> No Wikipedia article found for this topic.\n\n"
                f"## Overview\n\n"
                f"Explore this topic further by researching "
                f"{display_name} on Wikipedia or asking follow-up questions.\n\n"
            )

        content = page_to_markdown(page)
        logger.debug(
            "generate_library_content done (wikipedia) | topic=%s elapsed=%.2fs chars=%d pageid=%d",
            topic_name, elapsed, len(content), page.pageid,
        )
        return content

    except Exception as e:
        elapsed = time.perf_counter() - t0
        logger.error(
            "generate_library_content error | topic=%s elapsed=%.2fs error=%s",
            topic_name, elapsed, e,
        )
        return (
            f"# {display_name}\n\n"
            f"> Unable to fetch content for this topic.\n\n"
            f"## Overview\n\n"
            f"Research {display_name} on Wikipedia or ask follow-up questions.\n\n"
        )


def generate_topic_taxonomy(
    topic_name: str,
    library_content: str = "",
    conversation_text: str = "",
    model: Optional[str] = None,
) -> dict:
    """Generate parent/child/related topic taxonomy using Wikipedia.

    Resolves the topic name to a Wikipedia article and extracts
    categories (parent), linkshere (child), and links (related).
    """
    from app.services.wikipedia_service import resolve_page_sync, page_to_taxonomy

    t0 = time.perf_counter()
    display_name = topic_name.replace("-", " ").strip()
    empty_result = {"parent_topics": [], "child_topics": [], "related_topics": []}

    logger.debug("generate_topic_taxonomy start (wikipedia) | topic=%s", topic_name)

    try:
        page = resolve_page_sync(display_name)
        elapsed = time.perf_counter() - t0

        if page is None:
            logger.debug(
                "generate_topic_taxonomy no_article | topic=%s elapsed=%.2fs",
                topic_name, elapsed,
            )
            return empty_result

        result = page_to_taxonomy(page)
        total = sum(len(v) for v in result.values())
        logger.debug(
            "generate_topic_taxonomy done (wikipedia) | topic=%s elapsed=%.2fs "
            "parents=%d children=%d related=%d pageid=%d",
            topic_name, elapsed,
            len(result["parent_topics"]),
            len(result["child_topics"]),
            len(result["related_topics"]),
            page.pageid,
        )
        return result

    except Exception as e:
        elapsed = time.perf_counter() - t0
        logger.error(
            "generate_topic_taxonomy error | topic=%s elapsed=%.2fs error=%s",
            topic_name, elapsed, e,
        )
        return empty_result
