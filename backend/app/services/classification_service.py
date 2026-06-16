"""
Service for topic extraction from conversations.

Uses LLM for extraction with improved prompting, deduplication,
and confidence scoring.
"""

import logging
import re
import time
from difflib import SequenceMatcher
from typing import List, Set

from app.services.ai_service import chat_with_model_sync

logger = logging.getLogger(__name__)

MAX_PROMPT_CHARS = 4000
SIMILARITY_THRESHOLD = 0.75   # Merge topics above this similarity score

TOPIC_EXTRACTION_PROMPT = """Extract 3-8 distinct key topics from this conversation.
Return them as a JSON array with "name", "description", and "confidence" (0-1):

[
  {{"name": "quantum-computing", "description": "Uses quantum mechanics for computation, key concepts include superposition and entanglement", "confidence": 0.9}},
  {{"name": "qubits", "description": "Basic unit of quantum information, can represent 0 and 1 simultaneously unlike classical bits", "confidence": 0.8}}
]

Rules:
- Names must be short hyphenated slugs (3-5 words max)
- Descriptions must be 1-2 complete sentences, informative and standalone
- Confidence: 0.9+ for core topics discussed extensively, 0.5-0.8 for supporting topics
- Only return the JSON array, nothing else
- Do not include topics that are trivial, offhand mentions, or greetings

Conversation:
{conversation}

Topics (JSON array only):"""

# Simpler fallback prompt for models that struggle with structured output
TOPIC_EXTRACTION_FALLBACK = """List 3-5 important topics from this conversation.
One topic per line. Use this format: "topic-name - one sentence description"

Example:
quantum-computing - uses quantum mechanics for computation
qubits - basic unit of quantum information

Conversation:
{conversation}

Topics:"""


def _clean_topic_name(raw: str) -> str:
    """Convert a raw topic string into a clean lowercase-hyphenated slug."""
    s = str(raw).strip()
    s = re.sub(r'\*\*?|__?|`', '', s)
    s = re.sub(r'[\[\]{}()"\'#]', '', s)
    if ',' in s:
        s = s.split(',')[0].strip()
    s = ' '.join(s.split()).lower()
    s = re.sub(r'[^a-z0-9\s-]', '', s)
    s = re.sub(r'\s+', '-', s).strip('-')
    return s if s and len(s) > 1 else ''


def _parse_json_response(raw: str) -> List[dict]:
    """Parse LLM output as JSON, with fallback to line-by-line parsing."""
    import json

    # Try to extract a JSON array
    raw = raw.strip()
    # Remove markdown code fences if present
    raw = re.sub(r'^```(?:json)?\s*', '', raw)
    raw = re.sub(r'\s*```$', '', raw)

    # Try JSON parse
    try:
        data = json.loads(raw)
        if isinstance(data, list):
            topics = []
            for item in data:
                if isinstance(item, dict) and "name" in item:
                    name = _clean_topic_name(item["name"])
                    if name:
                        topics.append({
                            "name": name,
                            "description": str(item.get("description", "")).strip(),
                            "confidence": float(item.get("confidence", 0.5)),
                        })
            return topics
    except (json.JSONDecodeError, ValueError):
        pass

    # Fallback: line-by-line parsing
    topics: List[dict] = []
    seen: Set[str] = set()
    for line in raw.split('\n'):
        line = line.strip().strip(',').strip('"').strip("'")
        if not line:
            continue
        match = re.match(r'^(.+?)\s*[-–:]\s*(.+)$', line)
        if match:
            name = _clean_topic_name(match.group(1))
            desc = match.group(2).strip()
        else:
            name = _clean_topic_name(line)
            desc = ""
        if name and name not in seen:
            seen.add(name)
            topics.append({"name": name, "description": desc, "confidence": 0.5})
            if len(topics) >= 8:
                break

    return topics


def _similarity(a: str, b: str) -> float:
    """Compute string similarity between two topic names."""
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


def _deduplicate_topics(topics: List[dict]) -> List[dict]:
    """Merge near-duplicate topics, keeping the one with higher confidence."""
    if len(topics) <= 1:
        return topics

    merged = []
    used = set()

    for i, t1 in enumerate(topics):
        if i in used:
            continue
        best = t1
        for j, t2 in enumerate(topics):
            if j <= i or j in used:
                continue
            sim = _similarity(t1["name"], t2["name"])
            if sim >= SIMILARITY_THRESHOLD:
                # Merge: keep higher confidence, combine descriptions
                used.add(j)
                if t2["confidence"] > best["confidence"]:
                    best = t2
                # Combine descriptions if they differ meaningfully
                if t1["description"] and t2["description"]:
                    best = {
                        **best,
                        "description": t1["description"]
                        if len(t1["description"]) > len(t2["description"])
                        else t2["description"],
                    }
        merged.append(best)

    return merged


def extract_topics(conversation_text: str, use_fallback: bool = False) -> List[dict]:
    """Extract distinct topics with descriptions and confidence from a conversation.

    Tries the structured JSON prompt first. If it returns empty results and
    use_fallback is True, retries with a simpler line-by-line prompt that
    weaker models can handle.

    Returns a list of {"name": str, "description": str, "confidence": float} dicts.
    """
    t0 = time.perf_counter()
    conv = conversation_text[:MAX_PROMPT_CHARS]

    # Try the JSON prompt first
    prompt = TOPIC_EXTRACTION_PROMPT.format(conversation=conv)
    logger.debug("extract_topics start | prompt_chars=%d fallback=%s", len(prompt), use_fallback)

    try:
        response = chat_with_model_sync([{"role": "user", "content": prompt}])
        elapsed = time.perf_counter() - t0

        topics = _parse_json_response(response)

        # If JSON parsing produced nothing and fallback is enabled, try simpler prompt
        if not topics and use_fallback:
            logger.debug("extract_topics json_empty, trying fallback | elapsed=%.2fs", elapsed)
            fallback_prompt = TOPIC_EXTRACTION_FALLBACK.format(conversation=conv)
            try:
                fallback_response = chat_with_model_sync(
                    [{"role": "user", "content": fallback_prompt}]
                )
                topics = _parse_json_response(fallback_response)
            except Exception as fb_err:
                logger.warning("extract_topics fallback also failed: %s", fb_err)

        topics = _deduplicate_topics(topics)
        topics.sort(key=lambda t: t["confidence"], reverse=True)
        topics = topics[:8]

        logger.debug(
            "extract_topics done | elapsed=%.2fs topics=%d raw_len=%d",
            elapsed, len(topics), len(response),
        )
        return topics

    except Exception as e:
        elapsed = time.perf_counter() - t0
        logger.error("extract_topics error | elapsed=%.2fs error=%s", elapsed, e)
        return []
