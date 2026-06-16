"""
Topic enrichment service — generates structured library content and
parent/child/related topic taxonomies using the LLM.

Called when:
  1. A topic is classified from a conversation (library entry generation)
  2. A topic is explored/clicked (deep-dive library generation)
  3. Map suggestions are rebuilt (taxonomy extraction)

This replaces the old behavior of storing raw assistant message text
as library content with no structure.
"""

import json
import logging
import re
import time
from typing import List, Optional

from app.services.ai_service import generate_structured_json_sync, chat_with_model_sync

logger = logging.getLogger(__name__)

MAX_CONVERSATION_CHARS = 6000

# ─────────────────────────────────────────────────────────────────────
# Library Content Prompt — generates structured markdown with sections
# ─────────────────────────────────────────────────────────────────────

LIBRARY_CONTENT_PROMPT = """You are a knowledge librarian. Based on the conversation below,
write a structured markdown document about the topic "{topic_name}".

Use this EXACT format:

# {topic_name}

> Write a 1-2 sentence summary that captures the essence of this topic.

## Overview

Write 2-3 paragraphs explaining what this topic is, why it matters, and
its key characteristics. Be informative and educational.

## Key Concepts

- **Concept Name**: Brief 1-sentence explanation
- **Concept Name**: Brief 1-sentence explanation
(3-5 key concepts, each as a bullet with bold name)

## Use Cases

- Use case 1 — one sentence
- Use case 2 — one sentence
(2-4 realistic use cases)

Rules:
- Use EXACTLY the section headings shown above (## Overview, ## Key Concepts, ## Use Cases)
- Do NOT include Parent Topics, Child Topics, or Related Topics sections
- Keep descriptions in bullets to one sentence
- Do not include any text outside the document structure
- Do not wrap the output in code fences

Conversation:
{conversation}

Structured document:"""

# ─────────────────────────────────────────────────────────────────────
# Taxonomy Prompt — extracts parent/child/related from library content
# ─────────────────────────────────────────────────────────────────────

TAXONOMY_PROMPT = """Analyze this knowledge base entry about "{topic_name}" and identify
its parent topics (broader categories), child topics (narrower sub-topics),
and related topics (peers/alternatives).

Return ONLY a JSON object with this exact structure:

{{
  "parent_topics": [
    {{"name": "broader-category-name", "description": "One sentence why this is a parent"}}
  ],
  "child_topics": [
    {{"name": "sub-topic-name", "description": "One sentence what this sub-topic is"}}
  ],
  "related_topics": [
    {{"name": "related-topic-name", "description": "One sentence how it relates"}}
  ]
}}

Rules:
- Names must be short lowercase-hyphenated slugs (2-4 words)
- Descriptions must be 1 sentence
- 2-3 items per category
- If a category has no meaningful entries, return an empty array
- Only return the JSON, nothing else

Knowledge base entry:
{library_content}

JSON:"""

# Shorter prompt for when we have conversation but no library content yet
TAXONOMY_FROM_CONVERSATION_PROMPT = """Analyze this conversation about "{topic_name}" and identify
its parent topics (broader categories), child topics (narrower sub-topics),
and related topics (peers/alternatives).

Return ONLY a JSON object with this exact structure:

{{
  "parent_topics": [
    {{"name": "broader-category-name", "description": "One sentence why this is a parent"}}
  ],
  "child_topics": [
    {{"name": "sub-topic-name", "description": "One sentence what this sub-topic is"}}
  ],
  "related_topics": [
    {{"name": "related-topic-name", "description": "One sentence how it relates"}}
  ]
}}

Rules:
- Names must be short lowercase-hyphenated slugs (2-4 words)
- Descriptions must be 1 sentence
- 2-3 items per category
- If a category has no meaningful entries, return an empty array
- Only return the JSON, nothing else

Conversation:
{conversation}

JSON:"""

# ─────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────


def generate_library_content(
    topic_name: str,
    conversation_text: str,
    model: Optional[str] = None,
) -> str:
    """Generate a structured markdown library entry for a topic.

    Uses the LLM to produce a document with Overview, Key Concepts,
    Use Cases, Parent Topics, Child Topics, and Related Topics sections.

    Args:
        topic_name: Display name of the topic (e.g., "databricks")
        conversation_text: The conversation transcript to base content on
        model: Optional model override

    Returns:
        Structured markdown string with ## sections
    """
    t0 = time.perf_counter()
    display_name = topic_name.replace("-", " ").title()
    conv = conversation_text[:MAX_CONVERSATION_CHARS]

    prompt = LIBRARY_CONTENT_PROMPT.format(
        topic_name=display_name,
        conversation=conv,
    )

    logger.debug(
        "generate_library_content start | topic=%s prompt_chars=%d",
        topic_name, len(prompt),
    )

    try:
        content = chat_with_model_sync(
            [{"role": "user", "content": prompt}],
            model=model,
        )
        elapsed = time.perf_counter() - t0

        # Ensure the content starts with a heading
        if not content.strip().startswith("#"):
            content = f"# {display_name}\n\n> Auto-generated knowledge entry.\n\n{content}"

        logger.debug(
            "generate_library_content done | topic=%s elapsed=%.2fs chars=%d",
            topic_name, elapsed, len(content),
        )
        return content

    except Exception as e:
        elapsed = time.perf_counter() - t0
        logger.error(
            "generate_library_content error | topic=%s elapsed=%.2fs error=%s",
            topic_name, elapsed, e,
        )
        # Return a minimal fallback so the pipeline doesn't break
        return (
            f"# {display_name}\n\n"
            f"> Discussed in the conversation.\n\n"
            f"## Overview\n\n"
            f"The conversation covered {display_name}. "
            f"Explore this topic further by asking follow-up questions.\n\n"
        )


def generate_topic_taxonomy(
    topic_name: str,
    library_content: str = "",
    conversation_text: str = "",
    model: Optional[str] = None,
) -> dict:
    """Generate parent/child/related topic taxonomy for a topic.

    Uses the LLM to identify broader categories, narrower sub-topics,
    and related alternatives.

    Args:
        topic_name: Display name of the topic
        library_content: Existing library content (preferred source)
        conversation_text: Fallback conversation text if no library content
        model: Optional model override

    Returns:
        {
            "parent_topics": [{"name": str, "description": str}, ...],
            "child_topics": [{"name": str, "description": str}, ...],
            "related_topics": [{"name": str, "description": str}, ...],
        }
    """
    t0 = time.perf_counter()
    display_name = topic_name.replace("-", " ").title()
    empty_result = {"parent_topics": [], "child_topics": [], "related_topics": []}

    # Choose prompt based on available content
    if library_content and len(library_content.strip()) > 100:
        prompt = TAXONOMY_PROMPT.format(
            topic_name=display_name,
            library_content=library_content[:MAX_CONVERSATION_CHARS],
        )
    elif conversation_text:
        prompt = TAXONOMY_FROM_CONVERSATION_PROMPT.format(
            topic_name=display_name,
            conversation=conversation_text[:MAX_CONVERSATION_CHARS],
        )
    else:
        logger.debug("generate_topic_taxonomy skip | topic=%s no_content", topic_name)
        return empty_result

    logger.debug(
        "generate_topic_taxonomy start | topic=%s prompt_chars=%d",
        topic_name, len(prompt),
    )

    try:
        raw = generate_structured_json_sync(prompt, model=model)
        elapsed = time.perf_counter() - t0

        # Parse JSON response
        raw = raw.strip()
        raw = re.sub(r'^```(?:json)?\s*', '', raw)
        raw = re.sub(r'\s*```$', '', raw)

        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            logger.warning(
                "generate_topic_taxonomy json_parse_error | topic=%s raw=%s",
                topic_name, raw[:200],
            )
            return empty_result

        # Validate and normalize
        result = empty_result.copy()
        for key in ("parent_topics", "child_topics", "related_topics"):
            items = data.get(key, [])
            if isinstance(items, list):
                result[key] = [
                    {
                        "name": _normalize_topic_slug(item.get("name", "")),
                        "description": str(item.get("description", "")).strip(),
                    }
                    for item in items
                    if isinstance(item, dict) and item.get("name")
                ]

        total = sum(len(v) for v in result.values())
        logger.debug(
            "generate_topic_taxonomy done | topic=%s elapsed=%.2fs "
            "parents=%d children=%d related=%d",
            topic_name, elapsed,
            len(result["parent_topics"]),
            len(result["child_topics"]),
            len(result["related_topics"]),
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
