import uuid
import re
import random

from app.models.topic_edge import TopicEdge
from app.services.library_service import get_latest_library_entry_for_topic
from app.services.topic_service import (
    create_edge,
    create_topic,
    delete_propositions,
    get_topics,
    normalize_topic_name,
)

# ─── Suggestion kind labels (used on the frontend to tag suggestions) ───

SUGGESTION_KIND_PARENT = "parent"
SUGGESTION_KIND_CHILD = "child"
SUGGESTION_KIND_RELATED = "related"


def get_source_text_for_topic(db, topic) -> str:
    entry = get_latest_library_entry_for_topic(db, topic.id)
    if entry and entry.content.strip():
        return entry.content

    if topic.description and topic.description.strip():
        return topic.description

    return topic.name.replace("-", " ")


def _get_taxonomy_from_topic(topic) -> dict | None:
    """Extract taxonomy (parent/child/related) from a topic's taxonomy JSONB column.

    Returns None if taxonomy is not stored (e.g., topics created before this feature).
    """
    if not topic.taxonomy or not isinstance(topic.taxonomy, dict):
        return None
    tax = topic.taxonomy
    # Validate required keys exist
    if any(k in tax for k in ("parent_topics", "child_topics", "related_topics")):
        return tax
    return None


# ─── Section extractors: parse ## Parent Topics / ## Child Topics / ## Related Topics ───

def _extract_topic_bullets_from_section(source_text: str, section_name: str) -> list:
    """Extract topic bullets from a markdown ## section (e.g., '## Parent Topics').

    Returns a list of {"name": str, "description": str} dicts.
    """
    pattern = rf"(?ims)^##\s*{re.escape(section_name)}:?\s*$\s*(.*?)(?=^##\s+|\Z)"
    match = re.search(pattern, source_text)
    if not match:
        return []

    items = []
    seen = set()
    for line in match.group(1).splitlines():
        # Strip bullet markers: - * + or numbered
        cleaned = re.sub(r"^\s*(?:[-*+]|\d+[.)])\s*", "", line).strip()
        if not cleaned:
            continue

        # Split on " - " to separate name from description
        parts = cleaned.split(" - ", 1)
        raw_name = parts[0].strip()
        description = parts[1].strip() if len(parts) > 1 else ""

        # Clean and truncate name (max 100 chars before slugify, fits in 255 col)
        raw_name = re.sub(r'\*\*|__|`', '', raw_name)  # strip markdown bold/italic/code
        raw_name = raw_name[:100].strip()
        if not raw_name:
            continue

        normalized = normalize_topic_name(raw_name)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)

        items.append({
            "name": normalized.replace(" ", "-"),
            "description": description or f"Listed under {section_name}.",
        })

    return items


def _extract_parent_topics_from_library_entry(source_text: str) -> list:
    return _extract_topic_bullets_from_section(source_text, "Parent Topics")


def _extract_child_topics_from_library_entry(source_text: str) -> list:
    return _extract_topic_bullets_from_section(source_text, "Child Topics")


def _extract_related_topics_from_library_entry(source_text: str) -> list:
    return _extract_topic_bullets_from_section(source_text, "Related Topics")


# ─── Regex fallback for when the library entry doesn't have structured sections ───

def _extract_concrete_topics_from_text(source_topic, source_text: str, existing_topic_names: set) -> list:
    """Extract concrete follow-up topic suggestions directly from source text
    by finding key noun phrases, technologies, concepts, and named entities."""
    fallback_proposals = []
    seen = set()

    # Normalize the source topic name so we avoid repeating it
    source_words = set(normalize_topic_name(source_topic.name).split())

    # 1. Look for backtick-wrapped terms (e.g. `numpy`, `docker`) – common in AI output
    backtick_terms = re.findall(r'`([^`]+)`', source_text)
    for term in backtick_terms:
        clean = term.strip().lower().replace(" ", "-")
        norm = normalize_topic_name(clean)
        if (norm
            and norm not in existing_topic_names
            and norm not in seen
            and norm not in source_words
            and len(norm) > 2
            and len(fallback_proposals) < 3):
            seen.add(norm)
            fallback_proposals.append({
                "name": clean.replace(" ", "-"),
                "description": f"A referenced term in the conversation about {normalize_topic_name(source_topic.name)}.",
            })

    # 2. Extract capitalized multi-word phrases (likely proper nouns / technologies)
    if len(fallback_proposals) < 3:
        capitalized_phrases = re.findall(
            r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\b', source_text
        )
        for phrase in capitalized_phrases:
            clean = phrase.strip().lower().replace(" ", "-")
            norm = normalize_topic_name(clean)
            if (norm
                and norm not in existing_topic_names
                and norm not in seen
                and norm not in source_words
                and len(norm) > 2
                and len(fallback_proposals) < 3):
                seen.add(norm)
                fallback_proposals.append({
                    "name": clean.replace(" ", "-"),
                    "description": f"A key concept mentioned alongside {normalize_topic_name(source_topic.name)}.",
                })

    # 3. Extract single capitalized nouns (likely technologies, tools, libraries)
    if len(fallback_proposals) < 3:
        single_caps = re.findall(r'\b([A-Z][a-z]{2,})\b', source_text)
        for word in single_caps:
            clean = word.strip().lower()
            norm = normalize_topic_name(clean)
            if (norm
                and norm not in existing_topic_names
                and norm not in seen
                and norm not in source_words
                and len(norm) > 2
                and len(fallback_proposals) < 3):
                seen.add(norm)
                fallback_proposals.append({
                    "name": clean.replace(" ", "-"),
                    "description": f"Related topic extracted from the discussion of {normalize_topic_name(source_topic.name)}.",
                })

    return fallback_proposals


# ─── Main suggestion rebuild ──────────────────────────────────────────────

def rebuild_map_suggestions(db, brainstorm_id: uuid.UUID, commit: bool = True):
    """Rebuild proposition topics and suggestion edges for all main topics.

    For each main topic:
      1. Parse parent/child/related sections from the library entry
      2. Create proposition topics with labeled suggestion edges
      3. Fall back to regex extraction if library entry has no sections
    """
    main_topics = [topic for topic in get_topics(db, brainstorm_id) if not topic.is_proposition]

    db.query(TopicEdge).filter(
        TopicEdge.brainstorm_id == brainstorm_id,
        TopicEdge.relationship.in_([
            "suggestion",
            "suggestion:parent",
            "suggestion:child",
            "suggestion:related",
        ]),
    ).delete(synchronize_session=False)
    delete_propositions(db, brainstorm_id, commit=False)

    existing_topic_names = {
        normalize_topic_name(topic.name)
        for topic in main_topics
    }

    created_suggestions = []

    for source_topic in main_topics:
        # Prefer taxonomy JSONB column (fast, structured) over markdown parsing
        taxonomy = _get_taxonomy_from_topic(source_topic)
        if taxonomy:
            parent_proposals = taxonomy.get("parent_topics", [])
            child_proposals = taxonomy.get("child_topics", [])
            related_proposals = taxonomy.get("related_topics", [])
        else:
            # Fall back to regex parsing from markdown library entries
            source_text = get_source_text_for_topic(db, source_topic)
            parent_proposals = _extract_parent_topics_from_library_entry(source_text)
            child_proposals = _extract_child_topics_from_library_entry(source_text)
            related_proposals = _extract_related_topics_from_library_entry(source_text)

            # If no structured sections found, fall back to regex extraction
            all_structured = parent_proposals + child_proposals + related_proposals
            if not all_structured:
                fallback = _extract_concrete_topics_from_text(source_topic, source_text, existing_topic_names)
                if fallback:
                    related_proposals = random.sample(fallback, k=min(3, len(fallback)))

        # Create proposition topics with suggestion edges
        all_proposals = [
            (parent_proposals, SUGGESTION_KIND_PARENT),
            (child_proposals, SUGGESTION_KIND_CHILD),
            (related_proposals, SUGGESTION_KIND_RELATED),
        ]

        for proposals, kind in all_proposals:
            for proposal in proposals[:3]:
                candidate_name = normalize_topic_name(proposal.get("name", ""))
                if not candidate_name or candidate_name in existing_topic_names:
                    continue

                # Build a richer description that includes the kind label
                base_desc = proposal.get("description", "")
                kind_label = kind.replace("_", " ").title()
                description = f"[{kind_label}] {base_desc}" if base_desc else f"[{kind_label}] Suggested topic"

                proposition = create_topic(
                    db=db,
                    brainstorm_id=brainstorm_id,
                    name=candidate_name.replace(" ", "-"),
                    description=description,
                    is_proposition=True,
                    confidence=0.35,
                    commit=False,
                )
                existing_topic_names.add(candidate_name)
                create_edge(
                    db=db,
                    brainstorm_id=brainstorm_id,
                    source_topic_id=source_topic.id,
                    target_topic_id=proposition.id,
                    relationship=f"suggestion:{kind}",
                    weight=0.35,
                    commit=False,
                )
                created_suggestions.append(proposition)

    if commit:
        db.commit()

    return created_suggestions
