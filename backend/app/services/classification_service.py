"""
Service that classifies chat messages into topics and generates
library entries and map propositions using LangChain.
"""
import json
import logging
import re
from typing import List, Optional
from app.services.ai_service import chat_with_model_sync, generate_structured_json_sync

logger = logging.getLogger(__name__)

# Max chars of conversation text to include in LLM prompts
# Keeps prompt sizes predictable for local/cheap models with small context windows
MAX_PROMPT_CHARS = 3000
# Source text limit for map proposals — needs more room for full document content
MAX_SOURCE_CHARS = 6000


TOPIC_CLASSIFICATION_PROMPT = """You are a topic classification AI. Given a conversation between a user and an AI assistant, identify the main topic(s) discussed.

Return a JSON array of objects with:
- "name": short topic name (lowercase, hyphenated, e.g. "apache-airflow")
- "description": brief description of what was discussed
- "confidence": float between 0 and 1

Only return the JSON array, no other text.

Conversation:
{conversation}
"""


LIBRARY_ENTRY_PROMPT = """You are a knowledge documentation AI. Given a conversation about a topic, create a structured markdown document that captures the key information.

Create a markdown file with:
- Title: The topic name
- Metadata: date, related topics
- Prompt: The user's question/input
- Result: The AI's response
- Thinking Process: Key insights and reasoning
- Information Gathered: Facts, concepts, and resources mentioned

Return ONLY the markdown content, no other text.

Topic: {topic_name}
Conversation:
{conversation}
"""


MAP_PROPOSAL_PROMPT = """You are a knowledge mapping AI.

Given the source topic and the source content below, propose exactly 3 concrete follow-up topics that are directly grounded in the content.

Rules:
- Use specific concepts, entities, methods, or subproblems mentioned or strongly implied in the source content.
- Do NOT use generic placeholder labels like foundations, practical uses, or future directions.
- Do NOT repeat the source topic name.
- Prefer topics that would naturally be explored next after reading the source content.
- Return lowercase, hyphenated topic names.

Return a JSON array of objects with:
- "name": proposed topic name
- "description": one short sentence explaining why it follows from the source content

Only return the JSON array, no other text.

Source topic:
{source_topic_name}

Existing topic names to avoid:
{existing_topic_names}

Source content:
{source_text}
"""


def classify_topics(conversation_text: str) -> List[dict]:
    """Extract topics from a conversation."""
    prompt = TOPIC_CLASSIFICATION_PROMPT.format(conversation=conversation_text[:MAX_PROMPT_CHARS])
    try:
        # Use generate_structured_json_sync for Ollama JSON-forced output
        response = generate_structured_json_sync(prompt)
        json_match = re.search(r'\[.*\]', response, re.DOTALL)
        if json_match:
            topics = json.loads(json_match.group())
            return topics
        return []
    except Exception as e:
        logger.error("Topic classification failed", exc_info=True)
        return []


def generate_library_entry(topic_name: str, conversation_text: str) -> str:
    """Generate a markdown library entry for a topic."""
    prompt = LIBRARY_ENTRY_PROMPT.format(
        topic_name=topic_name,
        conversation=conversation_text[:MAX_PROMPT_CHARS],
    )
    try:
        response = chat_with_model_sync([{"role": "user", "content": prompt}])
        return response
    except Exception as e:
        logger.error("Library entry generation failed for topic '%s'", topic_name, exc_info=True)
        return f"# {topic_name}\n\n*Library entry could not be generated.*"


def propose_related_topics_from_content(
    source_topic_name: str,
    source_text: str,
    existing_topic_names: List[str] | None = None,
    max_topics: int = 3,
) -> List[dict]:
    """Propose concrete follow-up topics grounded in a source response or document."""
    prompt = MAP_PROPOSAL_PROMPT.format(
        source_topic_name=source_topic_name,
        existing_topic_names=json.dumps(existing_topic_names or [], indent=2),
        source_text=source_text[:MAX_SOURCE_CHARS],
    )
    try:
        # Use generate_structured_json_sync for Ollama JSON-forced output
        response = generate_structured_json_sync(prompt)
        json_match = re.search(r'\[.*\]', response, re.DOTALL)
        if json_match:
            proposals = json.loads(json_match.group())
            return proposals[:max_topics]
        return []
    except Exception as e:
        logger.warning("Map proposal generation failed for '%s'", source_topic_name, exc_info=True)
        return []
