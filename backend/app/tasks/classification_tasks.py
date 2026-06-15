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
        update_brainstorm_title(db, brainstorm_id, title_candidate["name"].replace("-", " ").title())

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

    # Use the last assistant response as the library entry — no re-summarization
    assistant_msgs = [m for m in messages if m.role.value == "assistant" and m.content.strip()]
    md_content = assistant_msgs[-1].content if assistant_msgs else f"# {promoted_topic.name}\n\n*No content yet.*"
    file_name = f"{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.md"
    entry = create_library_entry(
        db=db,
        brainstorm_id=brainstorm_id,
        topic_id=promoted_topic.id,
        folder_name=promoted_topic.name,
        file_name=file_name,
        content=md_content,
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

    Uses the simple comma-separated extraction (1 LLM call) and the
    last AI response as the library entry (no re-summarization).
    """
    topic_names = extract_topics(conversation_text)
    primary_topic_name = infer_primary_topic_name(messages)
    existing_topics = get_topics(db, brainstorm_id)
    existing_topic_names = {
        t.name.lower().replace(" ", "-")
        for t in existing_topics
        if not t.is_proposition
    }

    # Use the last assistant message as the library entry content
    assistant_msgs = [m for m in messages if m.role.value == "assistant" and m.content.strip()]
    assistant_content = assistant_msgs[-1].content if assistant_msgs else ""

    if not topic_names:
        if primary_topic_name:
            topic_names = [primary_topic_name.lower().replace(" ", "-")]
        else:
            return []

    created_topics = []
    for index, name in enumerate(topic_names):
        # Primary topic takes priority
        if index == 0 and primary_topic_name:
            name = primary_topic_name.lower().replace(" ", "-")

        if name in existing_topic_names:
            continue

        # First topic becomes a main node; rest become suggestion propositions
        is_prop = index > 0

        topic = create_topic(
            db=db,
            brainstorm_id=brainstorm_id,
            name=name,
            description=f"Explored during conversation.",
            is_proposition=is_prop,
            confidence=0.6 if not is_prop else 0.3,
            commit=False,
        )

        # Only create library entries for main topics (not propositions)
        if not is_prop:
            md_content = assistant_content if assistant_content else f"# {name}\n\n*This topic was discussed in the conversation.*"
            file_name = f"{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.md"
            entry = create_library_entry(
                db=db,
                brainstorm_id=brainstorm_id,
                topic_id=topic.id,
                folder_name=name,
                file_name=file_name,
                content=md_content,
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

    messages = (
        db.query(Message)
        .filter(Message.brainstorm_id == brainstorm_id)
        .order_by(Message.created_at)
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


@celery_app.task(bind=True, max_retries=3)
def process_message_classification(self, brainstorm_id_str: str):
    """
    Process a brainstorm's messages to:
    1. Classify topics
    2. Generate library entries
    3. Propose related topics for the map
    """
    brainstorm_id = uuid.UUID(brainstorm_id_str)
    db = SessionLocal()

    try:
        result = _process_message_classification(db, brainstorm_id)
        from app.services.realtime_service import publish_brainstorm_event
        publish_brainstorm_event("classification_complete", brainstorm_id, result)
        return result
    except Exception as e:
        from app.services.realtime_service import publish_brainstorm_event
        publish_brainstorm_event("classification_error", brainstorm_id, {"error": str(e)})
        self.retry(exc=e, countdown=60)
        return {"status": "error", "error": str(e)}
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
