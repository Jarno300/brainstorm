"""
Celery tasks for processing chat messages:
1. Classify topics from conversations
2. Generate library entries (markdown files)
3. Propose related topics for the map
"""
import logging
import time
import uuid
import re
from datetime import datetime, timezone
from app.tasks.celery_app import celery_app
from app.database import SessionLocal
from app.models.message import Message
from app.services.classification_service import extract_topics
from app.services.topic_service import (
    create_topic,
    get_topics,
    create_edge,
    get_topic_by_name,
    promote_topic_to_main,
    promote_suggestion_edges_to_related,
    normalize_topic_name,
)
from app.services.map_suggestion_service import rebuild_map_suggestions
from app.services.library_service import create_library_entry
from app.services.brainstorm_service import get_brainstorm, update_brainstorm_title
from app.services.topic_enrichment_service import (
    generate_library_content,
    generate_topic_taxonomy,
)

logger = logging.getLogger(__name__)


STOPWORDS = {
    "about",
    "also",
    "and",
    "around",
    "data",
    "for",
    "from",
    "how",
    "in",
    "into",
    "me",
    "of",
    "on",
    "please",
    "show",
    "tell",
    "the",
    "to",
    "what",
    "with",
    "would",
    "you",
}

PROMPT_TOPIC_PATTERNS = [
    r"^\s*(?:explain|tell me about|what is|describe)\s+(.+?)\s*[\.!?]*\s*$",
]


def _taxonomy_to_markdown(taxonomy: dict) -> str:
    """Convert a taxonomy dict to markdown sections for library entries."""
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


def clean_topic_candidate(candidate: str) -> str:
    cleaned = candidate.strip(" .,:;!?\"'()[]{}")
    cleaned = re.sub(r'\*\*?|__?|`', '', cleaned)   # strip markdown
    cleaned = re.sub(r"\b(?:please|kindly)\b", "", cleaned).strip()
    cleaned = re.sub(r"\s+", " ", cleaned)
    cleaned = re.sub(r"^(?:the|a|an)\s+", "", cleaned)
    cleaned = re.sub(r"\s+(?:please|thanks?|thank you)$", "", cleaned)
    return cleaned.strip()


def infer_primary_topic_name(messages) -> str | None:
    user_messages = [msg.content.strip() for msg in messages if msg.role.value == "user" and msg.content.strip()]
    if not user_messages:
        return None

    latest_user_message = user_messages[-1].lower()
    patterns = [
        r"\btell me about\s+(.+?)(?:\?|\.|!|$)",
        r"\bwhat is\s+(.+?)(?:\?|\.|!|$)",
        r"\bexplain\s+(.+?)(?:\?|\.|!|$)",
        r"\bdescribe\s+(.+?)(?:\?|\.|!|$)",
        r"\b(?:on|for|regarding)\s+(.+?)(?:\?|\.|!|$)",
    ]

    for pattern in patterns:
        match = re.search(pattern, latest_user_message)
        if match:
            candidate = clean_topic_candidate(match.group(1))
            if candidate and candidate not in STOPWORDS:
                return candidate

    fallback_phrase = clean_topic_candidate(latest_user_message)
    fallback_phrase = re.sub(r"^(?:what is|tell me about|explain|describe)\s+", "", fallback_phrase)
    if fallback_phrase and len(fallback_phrase.split()) > 1:
        return fallback_phrase

    for word in re.findall(r"[a-z][a-z0-9-]{2,}", latest_user_message):
        if word not in STOPWORDS:
            return word

    return None


def build_conversation_text(messages) -> str:
    conversation_parts = []
    for msg in messages:
        role_label = "User" if msg.role.value == "user" else "Assistant"
        conversation_parts.append(f"{role_label}: {msg.content}")

    return "\n\n".join(conversation_parts)


def get_latest_user_message(messages):
    for msg in reversed(messages):
        if msg.role.value == "user" and msg.content.strip():
            return msg
    return None


def extract_prompted_topic_name(message_text: str) -> str | None:
    lowered = message_text.strip().lower()
    for pattern in PROMPT_TOPIC_PATTERNS:
        match = re.match(pattern, lowered)
        if not match:
            continue
        candidate = match.group(1).strip(" .,:;!?\"'()[]{}")
        if candidate and candidate not in STOPWORDS:
            return normalize_topic_name(candidate)
    return None


def find_promotable_topic(db, brainstorm_id: uuid.UUID, message_text: str):
    topic_name = extract_prompted_topic_name(message_text)
    if not topic_name:
        return None

    return get_topic_by_name(db, brainstorm_id, topic_name, is_proposition=True)


def rebuild_propositions_and_title(db, brainstorm_id: uuid.UUID, title_candidate: dict | None = None, commit: bool = True):
    rebuild_map_suggestions(db, brainstorm_id, commit=False)

    brainstorm = get_brainstorm(db, brainstorm_id)
    if brainstorm and brainstorm.title == "New Brainstorm" and title_candidate:
        try:
            name = title_candidate.get("name", "")
            if name:
                update_brainstorm_title(db, brainstorm_id, name.replace("-", " ").title())
        except Exception as e:
            logger.warning("Failed to update brainstorm title from candidate %s: %s", title_candidate, e)

    if commit:
        db.commit()


def promote_clicked_suggestion(db, brainstorm_id: uuid.UUID, messages, conversation_text: str):
    latest_user_message = get_latest_user_message(messages)
    if not latest_user_message:
        return None

    topic = find_promotable_topic(db, brainstorm_id, latest_user_message.content)
    if not topic:
        return None

    promoted_topic = promote_topic_to_main(
        db=db,
        topic=topic,
        confidence=max(topic.confidence or 0.0, 0.6),
        commit=False,
    )

    # Generate structured library content via LLM instead of raw assistant dump
    enriched_content = generate_library_content(
        topic_name=promoted_topic.name,
        conversation_text=conversation_text,
    )

    # Append taxonomy sections from the LLM taxonomy service
    taxonomy = generate_topic_taxonomy(
        topic_name=promoted_topic.name,
        library_content=enriched_content,
        conversation_text=conversation_text,
    )
    if taxonomy:
        taxonomy_md = _taxonomy_to_markdown(taxonomy)
        if taxonomy_md:
            enriched_content += "\n\n" + taxonomy_md

    file_name = f"{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.md"
    entry = create_library_entry(
        db=db,
        brainstorm_id=brainstorm_id,
        topic_id=promoted_topic.id,
        folder_name=promoted_topic.name,
        file_name=file_name,
        content=enriched_content,
        commit=False,
    )

    promoted_topic.library_path = entry.file_path
    promote_suggestion_edges_to_related(db, brainstorm_id, promoted_topic.id, commit=False)
    rebuild_propositions_and_title(db, brainstorm_id, title_candidate={"name": promoted_topic.name})

    db.commit()
    db.refresh(promoted_topic)

    return promoted_topic


def create_topics_from_classification(db, brainstorm_id: uuid.UUID, messages, conversation_text: str):
    """Extract topics from conversation and create them with library entries.

    Uses the JSON extraction (1 LLM call) with fallback to line-by-line
    if the model can't produce structured JSON.
    For the primary topic, generates structured library content and
    taxonomy (parent/child/related topics).
    """
    topic_list = extract_topics(conversation_text, use_fallback=True)
    primary_topic_name = infer_primary_topic_name(messages)
    existing_topics = get_topics(db, brainstorm_id)
    existing_topic_names = {
        t.name.lower().replace(" ", "-")
        for t in existing_topics
        if not t.is_proposition
    }

    if not topic_list:
        if primary_topic_name:
            topic_list = [{"name": primary_topic_name.lower().replace(" ", "-"), "description": ""}]
        else:
            return []

    created_topics = []
    for index, topic_data in enumerate(topic_list):
        name = topic_data.get("name", "unknown")
        description = topic_data.get("description", "")
        confidence = float(topic_data.get("confidence", 0.5))

        # Primary topic takes priority
        if index == 0 and primary_topic_name:
            name = primary_topic_name.lower().replace(" ", "-")

        if name in existing_topic_names:
            continue

        # First topic is always the main node; everything else is a proposition
        is_prop = index > 0

        topic = create_topic(
            db=db,
            brainstorm_id=brainstorm_id,
            name=name,
            description=description if description else "Explored during conversation.",
            is_proposition=is_prop,
            confidence=confidence,
            commit=False,
        )

        # Generate structured library content for main topics
        if not is_prop:
            # Use LLM to generate structured markdown
            enriched = generate_library_content(
                topic_name=name,
                conversation_text=conversation_text,
            )

            # Append taxonomy sections so rebuild_map_suggestions can parse them
            taxonomy = generate_topic_taxonomy(
                topic_name=name,
                library_content=enriched,
                conversation_text=conversation_text,
            )
            if taxonomy:
                taxonomy_md = _taxonomy_to_markdown(taxonomy)
                if taxonomy_md:
                    enriched += "\n\n" + taxonomy_md

            file_name = f"{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.md"
            entry = create_library_entry(
                db=db,
                brainstorm_id=brainstorm_id,
                topic_id=topic.id,
                folder_name=name,
                file_name=file_name,
                content=enriched,
                commit=False,
            )
            topic.library_path = entry.file_path

        created_topics.append({
            "id": str(topic.id),
            "name": name,
            "library_path": topic.library_path or "",
            "is_proposition": is_prop,
        })
        existing_topic_names.add(name)

    # Create suggestion edges from the main topic to each proposition
    if created_topics:
        main_id = created_topics[0]["id"]
        for t in created_topics[1:]:
            if t.get("is_proposition"):
                create_edge(
                    db=db,
                    brainstorm_id=brainstorm_id,
                    source_topic_id=uuid.UUID(main_id),
                    target_topic_id=uuid.UUID(t["id"]),
                    relationship="suggestion",
                    weight=0.3,
                    commit=False,
                )

    rebuild_propositions_and_title(db, brainstorm_id, title_candidate=created_topics[0] if created_topics else None)
    db.commit()
    return created_topics


def _process_message_classification(db, brainstorm_id: uuid.UUID):
    """Run the classification pipeline against the supplied DB session."""
    t0 = time.perf_counter()
    logger.debug("classification_pipeline start | brainstorm_id=%s", brainstorm_id)

    # Load all messages for classification (up to 500 to keep prompt size reasonable)
    messages = (
        db.query(Message)
        .filter(Message.brainstorm_id == brainstorm_id)
        .order_by(Message.created_at)
        .limit(500)
        .all()
    )

    if not messages:
        logger.debug("classification_pipeline skip | brainstorm_id=%s no_messages", brainstorm_id)
        return {"status": "no_messages"}

    conversation_text = build_conversation_text(messages)
    logger.debug("classification_pipeline conv | brainstorm_id=%s msgs=%d chars=%d",
                 brainstorm_id, len(messages), len(conversation_text))

    promoted_topic = promote_clicked_suggestion(db, brainstorm_id, messages, conversation_text)
    if promoted_topic:
        elapsed = time.perf_counter() - t0
        logger.debug("classification_pipeline done  | brainstorm_id=%s elapsed=%.2fs promoted=%s",
                     brainstorm_id, elapsed, promoted_topic.name)
        return {
            "status": "success",
            "topics_created": 0,
            "promoted_topic": {
                "id": str(promoted_topic.id),
                "name": promoted_topic.name,
                "library_path": promoted_topic.library_path,
            },
        }

    created_topics = create_topics_from_classification(db, brainstorm_id, messages, conversation_text)
    if not created_topics:
        elapsed = time.perf_counter() - t0
        logger.warning("classification_pipeline fail | brainstorm_id=%s elapsed=%.2fs no_topics", brainstorm_id, elapsed)
        return {"status": "no_topics_found"}

    elapsed = time.perf_counter() - t0
    logger.debug("classification_pipeline done  | brainstorm_id=%s elapsed=%.2fs topics=%d",
                 brainstorm_id, elapsed, len(created_topics))
    return {
        "status": "success",
        "topics_created": len(created_topics),
        "topics": created_topics,
    }


@celery_app.task(bind=True, max_retries=2)
def process_message_classification(self, brainstorm_id_str: str):
    """
    Process a brainstorm's messages to:
    1. Classify topics
    2. Generate library entries
    3. Propose related topics for the map

    Publishes classification_complete or classification_error via Redis PubSub.
    """
    brainstorm_id = uuid.UUID(brainstorm_id_str)
    db = SessionLocal()

    try:
        result = _process_message_classification(db, brainstorm_id)
        from app.services.realtime_service import publish_brainstorm_event

        # Even "no_topics_found" is a valid outcome — not an error.
        # Only publish as error if the pipeline itself raised an exception.
        publish_brainstorm_event("classification_complete", brainstorm_id, result)
        return result

    except Exception as e:
        from app.services.realtime_service import publish_brainstorm_event
        import traceback

        error_type = type(e).__name__
        error_msg = str(e)[:500]
        trace = traceback.format_exc()[-500:]  # last 500 chars of stack trace

        logger.error(
            "classification_error | brainstorm=%s type=%s error=%s trace=%s",
            brainstorm_id, error_type, error_msg, trace,
        )

        publish_brainstorm_event("classification_error", brainstorm_id, {
            "error": error_msg,
            "stage": "classification_pipeline",
            "type": error_type,
            "retry": self.request.retries < self.max_retries,
            "trace": trace,
        })

        logger.error(
            "classification_task_error | brainstorm=%s type=%s error=%s",
            brainstorm_id, error_type, error_msg,
            exc_info=True,
        )

        logger.error(
            "classification_error | brainstorm=%s error=%s retries=%d/%d",
            brainstorm_id, error_msg, self.request.retries, self.max_retries,
        )

        # Only retry on transient errors (LLM timeout, DB connection)
        if "timeout" in error_msg.lower() or "connection" in error_msg.lower():
            raise self.retry(exc=e, countdown=30)

        return {"status": "error", "error": error_msg}
    finally:
        db.close()


def process_message_classification_sync(brainstorm_id_str: str, db=None):
    """Synchronously run message classification for immediate UI updates."""
    brainstorm_id = uuid.UUID(brainstorm_id_str)
    owns_db = db is None
    session = db or SessionLocal()

    try:
        return _process_message_classification(session, brainstorm_id)
    finally:
        if owns_db:
            session.close()
