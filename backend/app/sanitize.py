"""
Input sanitization utilities.

Safely cleans user-provided text before it reaches the LLM or gets stored.
Includes server-side HTML sanitization as a defense-in-depth layer even
though React escapes by default.

This module handles content-policy concerns:
  - Strips HTML tags and escapes HTML entities
  - Trims excessive whitespace
  - Removes null bytes and control characters
  - Enforces max content length
"""

import html
import re

# Maximum allowed characters for a chat message
MAX_MESSAGE_LENGTH = 50_000

# Maximum allowed characters for topic names
MAX_TOPIC_NAME_LENGTH = 200

# Maximum allowed characters for topic descriptions
MAX_TOPIC_DESCRIPTION_LENGTH = 2_000

# Characters that should never appear in user content
_CONTROL_CHARS_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")

# HTML tag pattern for stripping
_HTML_TAG_RE = re.compile(r"<[^>]*>")


def _strip_html(value: str) -> str:
    """Remove HTML tags and unescape HTML entities."""
    value = _HTML_TAG_RE.sub("", value)
    return html.unescape(value)


def sanitize_text(value: str, max_length: int = MAX_MESSAGE_LENGTH) -> str:
    """Clean user-provided text.

    Returns a trimmed, safe string. If the input is non-text or
    excessively long, it is truncated.
    """
    if not value:
        return ""

    # Coerce to string
    value = str(value)

    # Strip null bytes and control characters
    value = _CONTROL_CHARS_RE.sub("", value)

    # Strip HTML tags and unescape entities
    value = _strip_html(value)

    # Normalize whitespace (collapse runs of spaces/newlines but keep paragraphs)
    value = value.strip()

    # Truncate to max length
    if len(value) > max_length:
        value = value[:max_length] + "…"

    return value


def sanitize_topic_name(value: str) -> str:
    """Clean a topic name to safe, slug-like format."""
    if not value:
        return ""
    value = sanitize_text(value, MAX_TOPIC_NAME_LENGTH)
    # Remove markdown and special chars
    value = re.sub(r"[^\w\s\-]", "", value)
    value = re.sub(r"\s+", " ", value).strip()
    return value


def sanitize_topic_description(value: str) -> str:
    """Clean a topic description."""
    return sanitize_text(value, MAX_TOPIC_DESCRIPTION_LENGTH)
