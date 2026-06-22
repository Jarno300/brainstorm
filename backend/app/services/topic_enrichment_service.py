"""
Topic enrichment service — generates structured library content and
parent/child/related topic taxonomies from Wikipedia.

All functions use Wikipedia as the knowledge source, with graceful
fallbacks when no article exists.
"""

import logging
import time
from typing import Optional

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────


def generate_library_content(
    topic_name: str,
    conversation_text: str,
    model: Optional[str] = None,
) -> str:
    """Generate a structured markdown library entry for a topic using Wikipedia.

    Resolves the topic name to a Wikipedia article and produces a document
    with Overview, Key Concepts, Use Cases, and Source sections.

    Falls back to a minimal entry if Wikipedia has no article.

    Args:
        topic_name: Display name of the topic (e.g., "databricks")
        conversation_text: Unused (kept for API compatibility)
        model: Unused (kept for API compatibility)

    Returns:
        Structured markdown string with ## sections
    """
    from app.services.wikipedia_service import resolve_page_sync, page_to_markdown

    t0 = time.perf_counter()
    display_name = topic_name.replace("-", " ").title()

    logger.debug(
        "generate_library_content start (wikipedia) | topic=%s",
        topic_name,
    )

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

    Args:
        topic_name: Display name of the topic
        library_content: Unused (kept for API compatibility)
        conversation_text: Unused (kept for API compatibility)
        model: Unused (kept for API compatibility)

    Returns:
        {
            "parent_topics": [{"name": str, "description": str}, ...],
            "child_topics": [{"name": str, "description": str}, ...],
            "related_topics": [{"name": str, "description": str}, ...],
        }
    """
    from app.services.wikipedia_service import resolve_page_sync, page_to_taxonomy

    t0 = time.perf_counter()
    display_name = topic_name.replace("-", " ").title()
    empty_result = {"parent_topics": [], "child_topics": [], "related_topics": []}

    logger.debug(
        "generate_topic_taxonomy start (wikipedia) | topic=%s",
        topic_name,
    )

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


def _normalize_topic_slug(name: str) -> str:
    """Normalize a topic name into a lowercase-hyphenated slug."""
    if not name:
        return ""
    name = str(name).strip().lower()
    name = re.sub(r'[^a-z0-9\s-]', '', name)
    name = re.sub(r'\s+', '-', name).strip('-')
    return name[:100] if name else ""
