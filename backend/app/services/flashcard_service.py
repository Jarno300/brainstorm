"""
Flashcard service — SM-2 spaced repetition and LLM-powered card generation.

The SM-2 algorithm adjusts ease_factor, interval, and repetitions based on
a quality rating (0-5) from the user. Cards are due when next_review <= now.
"""

import uuid
import json
import logging
import re
from datetime import datetime, timezone
from typing import List, Optional, AsyncIterator

from sqlalchemy.orm import Session
from sqlalchemy import and_

from app.models.flashcard import Flashcard
from app.models.topic import Topic

logger = logging.getLogger(__name__)

# ─── SM-2 Spaced Repetition Algorithm ──────────────────────────

def sm2(
    quality: int,
    ease_factor: float = 2.5,
    interval: int = 1,
    repetitions: int = 0,
) -> dict:
    """Apply the SM-2 algorithm and return updated scheduling fields.

    Args:
        quality: 0-5 rating (0=blackout, 5=perfect)
        ease_factor: current ease factor (default 2.5)
        interval: current interval in days (default 1)
        repetitions: consecutive correct repetitions (default 0)

    Returns:
        dict with ease_factor, interval, repetitions, next_review
    """
    if quality >= 3:
        # Correct response
        if repetitions == 0:
            new_interval = 1
        elif repetitions == 1:
            new_interval = 6
        else:
            new_interval = round(interval * ease_factor)

        new_repetitions = repetitions + 1
    else:
        # Incorrect response — reset
        new_interval = 1
        new_repetitions = 0

    # Update ease factor (EF' = EF + (0.1 - (5 - q) * (0.08 + (5 - q) * 0.02)))
    new_ef = ease_factor + (0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02))
    if new_ef < 1.3:
        new_ef = 1.3

    next_review = datetime.now(timezone.utc)
    # Add interval days (simple day-based, not minute-precise)
    from datetime import timedelta
    next_review = next_review.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=new_interval)

    return {
        "ease_factor": new_ef,
        "interval": new_interval,
        "repetitions": new_repetitions,
        "next_review": next_review,
    }


# ─── Flashcard CRUD ────────────────────────────────────────────

def get_flashcards(
    db: Session,
    brainstorm_id: uuid.UUID,
) -> List[Flashcard]:
    """Get all flashcards for a brainstorm, ordered by creation time."""
    return (
        db.query(Flashcard)
        .filter(Flashcard.brainstorm_id == brainstorm_id)
        .order_by(Flashcard.created_at)
        .all()
    )


def get_due_flashcards(
    db: Session,
    brainstorm_id: uuid.UUID,
) -> List[Flashcard]:
    """Get flashcards due for review (next_review <= now)."""
    now = datetime.now(timezone.utc)
    return (
        db.query(Flashcard)
        .filter(
            Flashcard.brainstorm_id == brainstorm_id,
            Flashcard.next_review <= now,
        )
        .order_by(Flashcard.next_review)
        .all()
    )


def get_flashcard(db: Session, flashcard_id: uuid.UUID) -> Optional[Flashcard]:
    return db.query(Flashcard).filter(Flashcard.id == flashcard_id).first()


def apply_review(
    db: Session,
    flashcard_id: uuid.UUID,
    quality: int,
    commit: bool = True,
) -> Optional[Flashcard]:
    """Record a review and update SM-2 scheduling fields."""
    card = get_flashcard(db, flashcard_id)
    if not card:
        return None

    result = sm2(
        quality=quality,
        ease_factor=card.ease_factor,
        interval=card.interval,
        repetitions=card.repetitions,
    )

    card.ease_factor = result["ease_factor"]
    card.interval = result["interval"]
    card.repetitions = result["repetitions"]
    card.next_review = result["next_review"]
    card.last_reviewed = datetime.now(timezone.utc)

    if commit:
        db.commit()
        db.refresh(card)

    return card


def delete_flashcards_for_brainstorm(db: Session, brainstorm_id: uuid.UUID, commit: bool = True):
    """Delete all flashcards for a brainstorm (e.g., before regeneration)."""
    db.query(Flashcard).filter(Flashcard.brainstorm_id == brainstorm_id).delete(synchronize_session=False)
    if commit:
        db.commit()


def count_due(db: Session, brainstorm_id: uuid.UUID) -> int:
    """Count flashcards due for review."""
    now = datetime.now(timezone.utc)
    return (
        db.query(Flashcard)
        .filter(
            Flashcard.brainstorm_id == brainstorm_id,
            Flashcard.next_review <= now,
        )
        .count()
    )


# ─── Flashcard Generation Prompt ───────────────────────────────

FLASHCARD_GENERATION_PROMPT = """You are an expert educator creating flashcards for spaced repetition study.

Below is a knowledge map containing topic cards with descriptions and connections between them.
Generate 10-20 high-quality flashcards (question + answer pairs) that test the most important facts,
concepts, and relationships from this material.

Rules:
- Each flashcard should test ONE specific fact or concept (not multiple)
- Questions should be clear and unambiguous
- Answers should be concise (1-3 sentences) but complete
- Include cards that test relationships between connected topics
- Include cards that test definitions of key terms
- Avoid trivial or overly obscure facts
- Format each flashcard on TWO SEPARATE LINES:
  Q: <question>
  A: <answer>
- Do NOT put Q and A on the same line
- Separate flashcards with a blank line

Knowledge Map:
{map_content}

Generate flashcards now. Output ONLY the flashcards in Q/A format, one per line pair:"""


def build_map_context(db: Session, brainstorm_id: uuid.UUID) -> str:
    """Build a text representation of the knowledge map for the LLM prompt."""
    topics = (
        db.query(Topic)
        .filter(Topic.brainstorm_id == brainstorm_id, Topic.is_proposition == False)
        .all()
    )

    if not topics:
        return "(empty map)"

    lines = []
    for topic in topics:
        name = topic.name.replace("-", " ").title()
        desc = topic.description or "(no description)"
        lines.append(f"Topic: {name}")
        lines.append(f"  Description: {desc}")
        if topic.taxonomy:
            tax = topic.taxonomy
            if isinstance(tax, dict):
                parents = tax.get("parent_topics", [])
                children = tax.get("child_topics", [])
                related = tax.get("related_topics", [])
                if parents:
                    lines.append(f"  Parent of: {', '.join(p.get('name', '') for p in parents)}")
                if children:
                    lines.append(f"  Child of: {', '.join(c.get('name', '') for c in children)}")
                if related:
                    lines.append(f"  Related to: {', '.join(r.get('name', '') for r in related)}")
        lines.append("")

    return "\n".join(lines)


def parse_flashcards_from_response(text: str) -> list[dict]:
    """Parse Q/A pairs from the LLM response into a list of {question, answer} dicts."""
    cards = []
    lines = text.strip().split("\n")

    current_q = None
    current_a = None

    for line in lines:
        line = line.strip()
        if not line:
            # End of current pair
            if current_q and current_a:
                cards.append({"question": current_q, "answer": current_a})
            current_q = None
            current_a = None
            continue

        # Handle "Q: ... / A: ..." on a single line (some LLMs interpret the / literally)
        qa_oneline = re.match(
            r'^\s*Q\s*:\s*(.+?)\s*/\s*A\s*:\s*(.+?)\s*$',
            line, re.IGNORECASE
        )
        if qa_oneline:
            if current_q and current_a:
                cards.append({"question": current_q, "answer": current_a})
            current_q = qa_oneline.group(1).strip()
            current_a = qa_oneline.group(2).strip()
            continue

        if line.upper().startswith("Q:") or line.startswith("Q:"):
            # If we already have a pending pair, flush it
            if current_q and current_a:
                cards.append({"question": current_q, "answer": current_a})
            current_q = line[2:].strip() if line[1] == ":" else line.split(":", 1)[1].strip()
            current_a = None
        elif line.upper().startswith("A:") or line.startswith("A:"):
            current_a = line[2:].strip() if line[1] == ":" else line.split(":", 1)[1].strip()
        elif current_a is not None:
            # Continuation of answer
            current_a += " " + line
        elif current_q is not None:
            # Continuation of question
            current_q += " " + line

    # Flush final pair
    if current_q and current_a:
        cards.append({"question": current_q, "answer": current_a})

    return cards


def persist_flashcards(
    db: Session,
    brainstorm_id: uuid.UUID,
    cards: list[dict],
) -> int:
    """Persist generated flashcards to the database. Returns count created."""
    count = 0
    for card_data in cards:
        card = Flashcard(
            brainstorm_id=brainstorm_id,
            question=card_data["question"],
            answer=card_data["answer"],
        )
        db.add(card)
        count += 1
    db.commit()
    return count
