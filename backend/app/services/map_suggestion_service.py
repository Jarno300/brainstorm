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


def get_source_text_for_topic(db, topic) -> str:
    entry = get_latest_library_entry_for_topic(db, topic.id)
    if entry and entry.content.strip():
        return entry.content

    if topic.description and topic.description.strip():
        return topic.description

    return topic.name.replace("-", " ")


def _extract_related_topics_from_library_entry(source_text: str) -> list:
    """Pull the related-topics bullets from a library entry, if present."""
    match = re.search(
        r"(?ims)^##\s*Related Topics:\s*$\s*(.*?)(?=^##\s+|\Z)",
        source_text,
    )
    if not match:
        return []

    related_topics = []
    seen = set()
    for line in match.group(1).splitlines():
        cleaned = re.sub(r"^\s*[-*+]\s*", "", line).strip()
        if not cleaned:
            continue
        normalized = normalize_topic_name(cleaned)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        related_topics.append({
            "name": normalized.replace(" ", "-"),
            "description": f"Explore {cleaned} because it was listed in the library entry's related topics.",
        })

    return related_topics


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
                "description": f"Explore {clean} as it was referenced in the source content.",
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
                    "description": f"Dive deeper into {phrase}, a key concept referenced in the source.",
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
                    "description": f"Learn more about {word}, a topic mentioned in the source content.",
                })

    return fallback_proposals



def rebuild_map_suggestions(db, brainstorm_id: uuid.UUID, commit: bool = True):
    main_topics = [topic for topic in get_topics(db, brainstorm_id) if not topic.is_proposition]

    db.query(TopicEdge).filter(
        TopicEdge.brainstorm_id == brainstorm_id,
        TopicEdge.relationship == "suggestion",
    ).delete(synchronize_session=False)
    delete_propositions(db, brainstorm_id, commit=False)

    existing_topic_names = {
        normalize_topic_name(topic.name)
        for topic in main_topics
    }

    created_suggestions = []
    for source_topic in main_topics:
        source_text = get_source_text_for_topic(db, source_topic)

        proposals = _extract_related_topics_from_library_entry(source_text)
        if proposals:
            proposals = random.sample(proposals, k=min(3, len(proposals)))

        # Fallback to concrete suggestions extracted from source text — no LLM call
        if not proposals:
            proposals = _extract_concrete_topics_from_text(source_topic, source_text, existing_topic_names)


        for proposal in proposals[:3]:
            candidate_name = normalize_topic_name(proposal.get("name", ""))
            if not candidate_name or candidate_name in existing_topic_names:
                continue

            proposition = create_topic(
                db=db,
                brainstorm_id=brainstorm_id,
                name=candidate_name.replace(" ", "-"),
                description=proposal.get("description", ""),
                is_proposition=True,
                confidence=0.3,
                commit=False,
            )
            existing_topic_names.add(candidate_name)
            create_edge(
                db=db,
                brainstorm_id=brainstorm_id,
                source_topic_id=source_topic.id,
                target_topic_id=proposition.id,
                relationship="suggestion",
                weight=0.3,
                commit=False,
            )
            created_suggestions.append(proposition)

    if commit:
        db.commit()

    return created_suggestions
