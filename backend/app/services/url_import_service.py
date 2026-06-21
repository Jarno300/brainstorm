"""
URL import service — fetches a web page, extracts readable text content,
and creates a library entry with a summary.

Uses httpx for fetching, BeautifulSoup + lxml for content extraction.
"""

import logging
import uuid
from datetime import datetime, timezone
from typing import Optional
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup
from sqlalchemy.orm import Session

from app.services.library_service import create_library_entry

logger = logging.getLogger(__name__)

MAX_CONTENT_LENGTH = 50_000  # 50KB of extracted text
REQUEST_TIMEOUT = 15.0  # seconds

# Elements to strip before extracting text
STRIP_TAGS = {"script", "style", "nav", "footer", "header", "aside", "noscript", "iframe", "form"}


def _extract_readable_text(html: str, url: str) -> dict:
    """Extract title and readable text from an HTML page.

    Tries to find <article>, <main>, or falls back to <body>.
    Strips non-content elements. Returns {title, text, site_name}.
    """
    soup = BeautifulSoup(html, "lxml")

    # Title
    title = ""
    title_tag = soup.find("title")
    if title_tag:
        title = title_tag.get_text(strip=True)
    if not title:
        h1 = soup.find("h1")
        if h1:
            title = h1.get_text(strip=True)

    # Site name from Open Graph or domain
    site_name = ""
    og_site = soup.find("meta", property="og:site_name")
    if og_site and og_site.get("content"):
        site_name = og_site["content"].strip()
    if not site_name:
        parsed = urlparse(url)
        site_name = parsed.netloc.replace("www.", "")

    # Strip unwanted elements
    for tag_name in STRIP_TAGS:
        for el in soup.find_all(tag_name):
            el.decompose()

    # Try content-specific containers
    content_el = (
        soup.find("article")
        or soup.find("main")
        or soup.find(role="main")
        or soup.find("div", class_="content")
        or soup.find("div", id="content")
        or soup.body
    )

    if not content_el:
        return {"title": title, "text": "", "site_name": site_name}

    # Extract text with paragraph separation
    paragraphs = []
    for p in content_el.find_all(["p", "h1", "h2", "h3", "h4", "h5", "h6", "li"]):
        text = p.get_text(" ", strip=True)
        if text and len(text) > 20:  # skip very short lines
            if p.name.startswith("h"):
                paragraphs.append(f"## {text}")
            else:
                paragraphs.append(text)

    raw_text = "\n\n".join(paragraphs)

    # Truncate
    if len(raw_text) > MAX_CONTENT_LENGTH:
        raw_text = raw_text[:MAX_CONTENT_LENGTH] + "\n\n... (truncated)"

    return {"title": title, "text": raw_text, "site_name": site_name}


def _build_library_content(title: str, text: str, url: str, site_name: str) -> str:
    """Build a markdown library entry from extracted page content."""
    display_title = title or urlparse(url).path.strip("/") or "Web Page"
    lines = [
        f"# {display_title}",
        "",
        f"> Imported from [{site_name}]({url}) on {datetime.now(timezone.utc).strftime('%Y-%m-%d')}",
        "",
        "## Content",
        "",
    ]
    if text:
        lines.append(text)
    else:
        lines.append("*No readable content extracted from this page.*")

    return "\n".join(lines)


async def import_url(
    db: Session,
    brainstorm_id: uuid.UUID,
    url: str,
    topic_id: Optional[uuid.UUID] = None,
) -> dict:
    """Fetch a URL, extract readable text, and create a library entry.

    Args:
        db: Database session
        brainstorm_id: Target brainstorm
        url: The URL to import
        topic_id: Optional topic to associate the entry with

    Returns:
        {entry_id, title, text_length, site_name}
    """
    logger.info("url_import start | brainstorm=%s url=%s", brainstorm_id, url)

    # Fetch the page
    async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT, follow_redirects=True) as client:
        try:
            response = await client.get(
                url,
                headers={
                    "User-Agent": "Brainstorm/1.0 (knowledge-mapping-bot; +https://brainstorm.app)",
                    "Accept": "text/html,application/xhtml+xml",
                    "Accept-Language": "en",
                },
            )
            response.raise_for_status()
            html = response.text
        except httpx.HTTPError as e:
            logger.error("url_import fetch_error | url=%s error=%s", url, e)
            raise ValueError(f"Failed to fetch URL: {e}")
        except Exception as e:
            logger.error("url_import fetch_error | url=%s error=%s", url, e)
            raise ValueError(f"Failed to fetch URL: {e}")

    # Extract readable content
    extracted = _extract_readable_text(html, url)

    if not extracted["text"]:
        raise ValueError("No readable content found on this page.")

    # Build markdown
    content = _build_library_content(
        extracted["title"], extracted["text"], url, extracted["site_name"]
    )

    # Create library entry
    folder_name = extracted["title"] or urlparse(url).path.strip("/").replace("/", "-") or "Imports"
    # Clean folder name for filesystem safety
    folder_name = folder_name[:100].strip().replace("/", "-")

    file_name = f"{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.md"

    entry = create_library_entry(
        db=db,
        brainstorm_id=brainstorm_id,
        topic_id=topic_id,
        folder_name=folder_name,
        file_name=file_name,
        content=content,
        commit=True,
        source_type="url",
        source_id=url,
    )

    logger.info(
        "url_import done | brainstorm=%s url=%s title=%s chars=%d entry=%s",
        brainstorm_id, url, extracted["title"], len(extracted["text"]), entry.id,
    )

    return {
        "entry_id": str(entry.id),
        "title": extracted["title"],
        "text_length": len(extracted["text"]),
        "site_name": extracted["site_name"],
    }
