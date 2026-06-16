"""
Topic research service — deep research + knowledge map generation in one LLM call.

Replaces the old multi-step pipeline:
  1. chat_with_model  → chat response
  2. extract_topics   → topic names from conversation
  3. generate_library → markdown from conversation
  4. generate_taxonomy → parent/child/related from library

With a single research call that draws from the LLM's full knowledge,
not just the conversation transcript.
"""

import json
import logging
import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.topic import Topic
from app.services.ai_service import chat_with_model_sync
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

RESEARCH_PROMPT = """You are a knowledge researcher. Research the topic "{topic_name}" thoroughly.
Draw from your full knowledge base — not just a surface summary.

Return a single JSON object with the structure below. Every field is required.

{{
  "summary": "1-2 sentence overview capturing the essence of {topic_name}",
  "overview": "3-4 paragraphs comprehensive explanation. Cover: what it is, how it works, key characteristics, history, and why it matters. Minimum 150 words.",
  "key_concepts": [
    {{"name": "Concept Name", "description": "2-3 sentence explanation"}}
  ],
  "use_cases": [
    {{"name": "Use Case", "description": "2-3 sentence description"}}
  ],
  "parent_topics": [
    {{"name": "broader-field-slug", "description": "How this topic fits into or relates to this broader field"}}
  ],
  "child_topics": [
    {{"name": "sub-topic-slug", "description": "What this sub-topic is and its relationship to {topic_name}"}}
  ],
  "related_topics": [
    {{"name": "related-topic-slug", "description": "How this relates to, compares with, or complements {topic_name}"}}
  ]
}}

Rules:
- key_concepts: 4-6 entries, names in plain English (not slugs) with thorough descriptions
- use_cases: 2-4 entries with realistic scenarios
- parent_topics / child_topics / related_topics: 2-3 entries each
- Topic names in parent/child/related MUST be lowercase-hyphenated slugs (e.g., "data-engineering")
- DO NOT wrap the JSON in markdown code fences
- DO NOT include any text before or after the JSON
- Only return valid JSON"""


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


def _parse_research_response(raw: str) -> Optional[ResearchResult]:
    """Parse the LLM's JSON response into a ResearchResult."""
    raw = raw.strip()
    raw = re.sub(r'^```(?:json)?\s*', '', raw)
    raw = re.sub(r'\s*```$', '', raw)

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        logger.warning("research parse error: %s | raw_preview=%s", e, raw[:200])
        return None

    if not isinstance(data, dict):
        return None

    def _list_of_dicts(key: str) -> List[dict]:
        items = data.get(key, [])
        if not isinstance(items, list):
            return []
        return [
            {"name": str(item.get("name", "")), "description": str(item.get("description", ""))}
            for item in items
            if isinstance(item, dict) and item.get("name")
        ]

    return ResearchResult(
        summary=str(data.get("summary", "")),
        overview=str(data.get("overview", "")),
        key_concepts=_list_of_dicts("key_concepts"),
        use_cases=_list_of_dicts("use_cases"),
        parent_topics=_list_of_dicts("parent_topics"),
        child_topics=_list_of_dicts("child_topics"),
        related_topics=_list_of_dicts("related_topics"),
    )


def _research_to_markdown(topic_name: str, result: ResearchResult, library_content: str = "") -> str:
    """Convert a ResearchResult into structured markdown for the library entry.

    The library_content parameter can contain additional LLM-generated content
    to prepend. If empty, builds the entire document from ResearchResult.
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

    # Taxonomy sections — always from ResearchResult
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


def research_topic(
    topic_name: str,
    model: Optional[str] = None,
) -> Optional[ResearchResult]:
    """Research a topic with a single LLM call.

    Returns a ResearchResult with overview, key concepts, use cases,
    and parent/child/related taxonomy — or None on failure.
    """
    t0 = time.perf_counter()
    display = topic_name.replace("-", " ").title()

    prompt = RESEARCH_PROMPT.format(topic_name=display)
    logger.debug("research_topic start | topic=%s prompt_chars=%d", topic_name, len(prompt))

    try:
        raw = chat_with_model_sync([{"role": "user", "content": prompt}], model=model)
        elapsed = time.perf_counter() - t0

        result = _parse_research_response(raw)
        if result is None:
            logger.warning(
                "research_topic parse_failed | topic=%s elapsed=%.2fs raw_preview=%s",
                topic_name, elapsed, raw[:200],
            )
            return None

        logger.debug(
            "research_topic done | topic=%s elapsed=%.2fs "
            "concepts=%d use_cases=%d parents=%d children=%d related=%d",
            topic_name, elapsed,
            len(result.key_concepts), len(result.use_cases),
            len(result.parent_topics), len(result.child_topics), len(result.related_topics),
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
    )
    primary.library_path = entry.file_path

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
