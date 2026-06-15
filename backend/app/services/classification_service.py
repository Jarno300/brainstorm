"""
Service for topic extraction from conversations.

Architecture: we avoid complex structured output (JSON arrays with
confidence scores) that weak local models can't produce reliably.
Instead, we ask for a simple comma-separated list and parse it.

Library entries reuse the AI's chat response directly — no
re-summarization needed. Map suggestions use regex extraction
from content (see map_suggestion_service).
"""
import logging
import re
import time
from typing import List

from app.services.ai_service import chat_with_model_sync

logger = logging.getLogger(__name__)

# Max chars of conversation to include in the prompt
MAX_PROMPT_CHARS = 4000


TOPIC_EXTRACTION_PROMPT = """Extract 2-5 key topics from this conversation.
Return ONLY lowercase comma-separated keywords. No descriptions, no markdown.

Example output: quantum-computing, qubits, superposition, entanglement

Conversation:
{conversation}

Topics:"""


def _clean_topic_name(raw: str) -> str:
    """Convert a raw topic string into a clean lowercase-hyphenated slug."""
    s = str(raw).strip()
    # Strip markdown and punctuation
    s = re.sub(r'\*\*?|__?|`', '', s)
    s = re.sub(r'[\[\]{}()"\'#]', '', s)
    # Take first item if comma-separated
    if ',' in s:
        s = s.split(',')[0].strip()
    # Normalize
    s = ' '.join(s.split()).lower()
    s = re.sub(r'[^a-z0-9\s-]', '', s)
    s = re.sub(r'\s+', '-', s).strip('-')
    return s if s and len(s) > 1 else ''


def extract_topics(conversation_text: str) -> List[str]:
    """Extract topic keywords from a conversation.

    Asks the LLM for a comma-separated list — no JSON, no confidence
    scores, no descriptions. Even a 1B model can handle this reliably.

    Returns a list of clean lowercase-hyphenated topic slugs.
    """
    t0 = time.perf_counter()
    conv = conversation_text[:MAX_PROMPT_CHARS]
    prompt = TOPIC_EXTRACTION_PROMPT.format(conversation=conv)
    logger.debug("extract_topics start | prompt_chars=%d", len(prompt))

    try:
        response = chat_with_model_sync([{"role": "user", "content": prompt}])
        elapsed = time.perf_counter() - t0

        names: List[str] = []
        seen = set()
        for part in response.split(','):
            name = _clean_topic_name(part)
            if name and name not in seen:
                seen.add(name)
                names.append(name)
                if len(names) >= 5:
                    break

        logger.debug("extract_topics done  | elapsed=%.2fs topics=%d raw=%.120s",
                     elapsed, len(names), response)
        return names

    except Exception as e:
        elapsed = time.perf_counter() - t0
        logger.error("extract_topics error | elapsed=%.2fs error=%s", elapsed, e)
        return []
