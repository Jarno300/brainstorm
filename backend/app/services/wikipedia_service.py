"""
Wikipedia service — factual knowledge retrieval from the Wikipedia Action API.

Replaces LLM calls for structured knowledge lookups. Uses httpx.AsyncClient,
in-memory TTL caching, and parallel API calls for fast page assembly.

Endpoints used (all Action API — w/api.php):
  - action=query&list=search          → topic disambiguation
  - action=query&prop=extracts        → page text (lead or full)
  - action=query&prop=categories      → parent topics (filtered)
  - action=query&prop=links           → related topics
  - action=query&prop=linkshere       → child topics
  - action=parse&prop=sections        → section headings for key concepts
  - action=parse&prop=text&section=N  → individual section text
  - action=query&prop=pageimages      → thumbnail

No API key required. Rate limits are generous for research-tool usage.
"""

import asyncio
import logging
import re
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional

import httpx

from app.services.topic_research_service import ResearchResult

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────
# Configuration
# ─────────────────────────────────────────────────────────────────────

WIKIPEDIA_BASE_URL = "https://en.wikipedia.org/w/api.php"
WIKIPEDIA_USER_AGENT = "Brainstorm/1.0 (https://github.com/brainstorm; knowledge-research-tool)"
WIKIPEDIA_TIMEOUT = 15  # seconds per request

# In-memory cache with TTL (24 hours for Wikipedia articles)
_CACHE: Dict[str, tuple[float, object]] = {}
_CACHE_TTL = 86400  # 24 hours in seconds

# Categories to exclude (Wikipedia maintenance / meta categories)
_EXCLUDED_CATEGORY_PREFIXES = (
    "All Wikipedia", "All articles", "Articles with", "Articles containing",
    "CS1", "Wikipedia", "Webarchive", "Commons", "Use ", "Use dmy",
    "Pages ", "Short description", "Coordinates",
)

# Section titles that typically contain "use cases" or "applications"
_USE_CASE_SECTION_TITLES = (
    "Applications", "Uses", "Use cases", "Usage", "Examples",
    "Applications and uses", "Real-world applications",
    "Practical applications", "Commercial applications",
)

# ─────────────────────────────────────────────────────────────────────
# Data types
# ─────────────────────────────────────────────────────────────────────

@dataclass
class WikipediaPage:
    """Structured data extracted from a Wikipedia article."""
    title: str
    pageid: int
    summary: str             # First paragraph (1-2 sentences)
    overview: str            # Full lead section (2-4 paragraphs)
    description: str         # Short Wikidata description
    sections: List[dict]     # [{toclevel, line, index}, ...]
    categories: List[str]    # Filtered topical categories
    links: List[str]         # Outgoing page links (related topics)
    linkshere: List[str]     # Incoming links (child topics)
    full_text: str           # Complete article text
    image_url: str           # Thumbnail URL or empty string
    section_texts: Dict[str, str] = field(default_factory=dict)  # {section_index: plain_text}


@dataclass
class SearchResult:
    """A single search result from Wikipedia."""
    title: str
    pageid: int
    snippet: str             # HTML snippet with <span class="searchmatch">
    wordcount: int
    size: int


# ─────────────────────────────────────────────────────────────────────
# Caching
# ─────────────────────────────────────────────────────────────────────

def _cache_key(endpoint: str, params: dict) -> str:
    """Build a deterministic cache key from endpoint + sorted params."""
    param_str = "&".join(
        f"{k}={v}" for k, v in sorted(params.items())
        if k not in ("format",)
    )
    return f"{endpoint}:{param_str}"


def _cache_get(key: str) -> Optional[object]:
    """Get a cached value if still valid. Returns None on miss or expiry."""
    entry = _CACHE.get(key)
    if entry is None:
        return None
    ts, value = entry
    if time.monotonic() - ts > _CACHE_TTL:
        del _CACHE[key]
        return None
    return value


def _cache_set(key: str, value: object) -> None:
    """Store a value in the cache with current timestamp."""
    _CACHE[key] = (time.monotonic(), value)


def clear_cache() -> None:
    """Clear the entire Wikipedia cache (useful for testing)."""
    _CACHE.clear()


# ─────────────────────────────────────────────────────────────────────
# API Helpers
# ─────────────────────────────────────────────────────────────────────

async def _api_get(params: dict, timeout: int = WIKIPEDIA_TIMEOUT) -> dict:
    """Make a GET request to the Wikipedia Action API. Returns parsed JSON."""
    cache_key = _cache_key("api", params)

    cached = _cache_get(cache_key)
    if cached is not None:
        logger.debug("wikipedia cache hit | key=%s", cache_key)
        return cached

    t0 = time.perf_counter()
    headers = {
        "User-Agent": WIKIPEDIA_USER_AGENT,
        "Accept": "application/json",
    }
    params_with_format = {**params, "format": "json"}

    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.get(
            WIKIPEDIA_BASE_URL,
            params=params_with_format,
            headers=headers,
        )
        response.raise_for_status()
        data = response.json()

    elapsed = time.perf_counter() - t0
    _cache_set(cache_key, data)
    logger.debug("wikipedia api call | params=%s elapsed=%.2fs", list(params.keys()), elapsed)
    return data


def _filter_categories(categories: List[str]) -> List[str]:
    """Remove maintenance/meta categories, keep only topical ones."""
    result = []
    for cat in categories:
        # Strip "Category:" prefix first
        clean = cat.replace("Category:", "")
        if not clean:
            continue
        if clean.startswith(_EXCLUDED_CATEGORY_PREFIXES):
            continue
        result.append(clean)
    return result


def _filter_links(links: List[str]) -> List[str]:
    """Filter out non-topic links (lists, disambiguation, etc.)."""
    skip_patterns = (
        "List of", "Lists of", "Outline of", "Index of",
        "Glossary of", "Timeline of", "History of",
        " (disambiguation)", "(disambiguation)",
    )
    result = []
    for link in links:
        if link.startswith(skip_patterns) or "(disambiguation)" in link:
            continue
        result.append(link)
    return result


def _parse_sections(sections_data: list) -> list:
    """Extract relevant section metadata from parse API response."""
    result = []
    for s in sections_data:
        if not isinstance(s, dict):
            continue
        line = s.get("line", "")
        toclevel = s.get("toclevel", 1)
        index = s.get("index", "")
        number = s.get("number", "")
        if line and index:
            result.append({
                "toclevel": int(toclevel),
                "line": line,
                "index": index,
                "number": number,
            })
    return result


def _clean_snippet(html_snippet: str) -> str:
    """Strip HTML from a search result snippet."""
    return re.sub(r"<[^>]+>", "", html_snippet).strip()


def _slugify(name: str) -> str:
    """Convert a topic name into a lowercase-hyphenated slug."""
    name = str(name).strip().lower()
    name = re.sub(r"'s\b", "", name)           # remove possessives
    name = re.sub(r"[^a-z0-9\s-]", "", name)   # strip non-alphanumeric
    name = re.sub(r"\s+", "-", name).strip("-")
    return name[:120] if name else ""


# ─────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────

async def search(query: str, limit: int = 5) -> List[SearchResult]:
    """Search Wikipedia for a topic name. Used for disambiguation.

    Args:
        query: Free-text search query (e.g., "transformer neural network")
        limit: Maximum number of results (default 5)

    Returns:
        List of SearchResult objects, best match first.
    """
    t0 = time.perf_counter()
    logger.debug("wikipedia search | query=%s limit=%d", query, limit)

    try:
        data = await _api_get({
            "action": "query",
            "list": "search",
            "srsearch": query,
            "srlimit": str(limit),
        })

        results = []
        for item in data.get("query", {}).get("search", []):
            results.append(SearchResult(
                title=item.get("title", ""),
                pageid=item.get("pageid", 0),
                snippet=_clean_snippet(item.get("snippet", "")),
                wordcount=item.get("wordcount", 0),
                size=item.get("size", 0),
            ))

        elapsed = time.perf_counter() - t0
        logger.debug("wikipedia search done | query=%s results=%d elapsed=%.2fs",
                     query, len(results), elapsed)
        return results

    except Exception as e:
        elapsed = time.perf_counter() - t0
        logger.error("wikipedia search error | query=%s elapsed=%.2fs error=%s",
                     query, elapsed, e)
        return []


async def get_page(title: str) -> Optional[WikipediaPage]:
    """Fetch a complete Wikipedia page with all metadata.

    Makes 5-7 parallel API calls for efficiency:
      - extract (lead section)
      - full text
      - categories
      - links
      - linkshere
      - sections
      - page image (best-effort)

    Args:
        title: Exact Wikipedia article title (use search() first for disambiguation)

    Returns:
        WikipediaPage if found, None if article doesn't exist.
    """
    t0 = time.perf_counter()
    logger.debug("wikipedia get_page | title=%s", title)

    try:
        # Run all queries in parallel
        extract_task = _api_get({
            "action": "query",
            "prop": "extracts",
            "exintro": "1",
            "explaintext": "1",
            "titles": title,
        })
        full_text_task = _api_get({
            "action": "query",
            "prop": "extracts",
            "explaintext": "1",
            "titles": title,
        })
        categories_task = _api_get({
            "action": "query",
            "prop": "categories",
            "titles": title,
            "cllimit": "30",
        })
        links_task = _api_get({
            "action": "query",
            "prop": "links",
            "titles": title,
            "pllimit": "50",
            "plnamespace": "0",
        })
        linkshere_task = _api_get({
            "action": "query",
            "prop": "linkshere",
            "titles": title,
            "lhlimit": "50",
            "lhnamespace": "0",
        })
        sections_task = _api_get({
            "action": "parse",
            "page": title,
            "prop": "sections",
        })
        image_task = _api_get({
            "action": "query",
            "prop": "pageimages",
            "titles": title,
            "pithumbsize": "200",
        })

        (
            extract_data,
            full_text_data,
            categories_data,
            links_data,
            linkshere_data,
            sections_data,
            image_data,
        ) = await asyncio.gather(
            extract_task, full_text_task, categories_task,
            links_task, linkshere_task, sections_task, image_task,
        )

        # ── Extract page data ──────────────────────────────────────
        pages = extract_data.get("query", {}).get("pages", {})
        if not pages:
            return None

        # Handle "missing" page (invalid title)
        first_page = next(iter(pages.values()))
        if first_page.get("missing") or first_page.get("invalid"):
            logger.debug("wikipedia get_page miss | title=%s", title)
            return None

        pageid = first_page.get("pageid", 0)
        page_title = first_page.get("title", title)

        # Extract
        overview = first_page.get("extract", "")
        # Summary = first paragraph of overview
        paragraphs = overview.split("\n")
        summary = paragraphs[0].strip() if paragraphs else ""

        # Description (short Wikidata description, if available)
        description = first_page.get("description", "")

        # Full text
        ft_pages = full_text_data.get("query", {}).get("pages", {})
        ft_page = next(iter(ft_pages.values()), {})
        full_text = ft_page.get("extract", overview)

        # Categories
        cat_pages = categories_data.get("query", {}).get("pages", {})
        cat_page = next(iter(cat_pages.values()), {})
        raw_cats = [
            c.get("title", "")
            for c in cat_page.get("categories", [])
        ]
        categories = _filter_categories(raw_cats)

        # Links (related topics)
        lnk_pages = links_data.get("query", {}).get("pages", {})
        lnk_page = next(iter(lnk_pages.values()), {})
        raw_links = [
            l.get("title", "")
            for l in lnk_page.get("links", [])
        ]
        links = _filter_links(raw_links)

        # Linkshere (child topics)
        lh_pages = linkshere_data.get("query", {}).get("pages", {})
        lh_page = next(iter(lh_pages.values()), {})
        raw_linkshere = [
            l.get("title", "")
            for l in lh_page.get("linkshere", [])
        ]
        linkshere = _filter_links(raw_linkshere)

        # Sections — fetch text for each H2 section for richer card content
        sections = _parse_sections(
            sections_data.get("parse", {}).get("sections", [])
        )

        # Fetch section texts for H2 sections (toclevel=1), excluding meta sections
        skip_titles = {
            "see also", "references", "notes", "further reading",
            "external links", "bibliography", "footnotes", "citation",
        }
        skip_titles.update(t.lower() for t in _USE_CASE_SECTION_TITLES)
        h2_indices = [
            s["index"] for s in sections
            if s.get("toclevel") == 1
            and s.get("line", "").strip().lower() not in skip_titles
        ]
        section_texts = {}
        if h2_indices:
            section_texts = await get_page_section_texts(page_title, h2_indices)

        # Image
        img_pages = image_data.get("query", {}).get("pages", {})
        img_page = next(iter(img_pages.values()), {})
        image_url = img_page.get("thumbnail", {}).get("source", "")

        page = WikipediaPage(
            title=page_title,
            pageid=pageid,
            summary=summary,
            overview=overview,
            description=description,
            sections=sections,
            section_texts=section_texts,
            categories=categories,
            links=links,
            linkshere=linkshere,
            full_text=full_text,
            image_url=image_url,
        )

        elapsed = time.perf_counter() - t0
        logger.debug(
            "wikipedia get_page done | title=%s elapsed=%.2fs "
            "overview_chars=%d sections=%d categories=%d links=%d linkshere=%d",
            title, elapsed, len(overview), len(sections),
            len(categories), len(links), len(linkshere),
        )
        return page

    except httpx.HTTPStatusError as e:
        elapsed = time.perf_counter() - t0
        if e.response.status_code == 404:
            logger.debug("wikipedia get_page 404 | title=%s", title)
            return None
        logger.error("wikipedia get_page http_error | title=%s status=%d elapsed=%.2fs",
                     title, e.response.status_code, elapsed)
        return None
    except Exception as e:
        elapsed = time.perf_counter() - t0
        logger.error("wikipedia get_page error | title=%s elapsed=%.2fs error=%s",
                     title, elapsed, e)
        return None


async def get_section_text(title: str, section_index: int) -> str:
    """Fetch the plain text of a specific section by its index.

    Args:
        title: Wikipedia article title
        section_index: Section index from the sections list (e.g., "1", "3")

    Returns:
        Plain text content of the section, or empty string on failure.
    """
    try:
        data = await _api_get({
            "action": "parse",
            "page": title,
            "prop": "text",
            "section": str(section_index),
        })
        html = data.get("parse", {}).get("text", {}).get("*", "")

        # Strip HTML tags to get plain text
        text = re.sub(r"<[^>]+>", " ", html)
        text = re.sub(r"\s+", " ", text)
        return text.strip()

    except Exception as e:
        logger.error("wikipedia get_section_text error | title=%s section=%s error=%s",
                     title, section_index, e)
        return ""


async def get_page_section_texts(title: str, section_indices: List[str]) -> Dict[str, str]:
    """Fetch text for multiple sections in parallel.

    Args:
        title: Wikipedia article title
        section_indices: List of section indices (e.g., ["1", "2", "3"])

    Returns:
        Dict mapping section index to plain text content.
    """
    if not section_indices:
        return {}

    tasks = [
        get_section_text(title, idx)
        for idx in section_indices
    ]
    results = await asyncio.gather(*tasks)
    return dict(zip(section_indices, results))


# ─────────────────────────────────────────────────────────────────────
# Sync wrappers — bridge async Wikipedia API to sync callers
# ─────────────────────────────────────────────────────────────────────

def _run_async(coro):
    """Run an async coroutine synchronously.

    Uses asyncio.run() which creates a fresh event loop each call.
    Safe for Celery tasks and FastAPI sync endpoints (where no loop is running).
    """
    return asyncio.run(coro)


def search_sync(query: str, limit: int = 5) -> List[SearchResult]:
    """Synchronous wrapper for search()."""
    return _run_async(search(query, limit))


def get_page_sync(title: str) -> Optional[WikipediaPage]:
    """Synchronous wrapper for get_page()."""
    return _run_async(get_page(title))


def resolve_page_sync(topic_name: str) -> Optional[WikipediaPage]:
    """Resolve a topic name to a Wikipedia page via search + fetch.

    This is the primary entry point for the knowledge pipeline:
      1. Try exact title lookup first (fast path)
      2. Fall back to search + pick best match
      3. Return WikipediaPage or None

    Args:
        topic_name: A human-readable topic name (e.g., "quantum computing",
                    "transformer neural network", "machine-learning")

    Returns:
        WikipediaPage if found, None if no article exists.
    """
    display = topic_name.replace("-", " ").strip()
    logger.debug("resolve_page_sync | topic=%s", topic_name)

    # Fast path: try exact Wikipedia title format
    exact_title = display.title()
    page = get_page_sync(exact_title)
    if page is not None:
        return page

    # Also try with underscores
    alt_title = display.replace(" ", "_")
    if alt_title != exact_title:
        page = get_page_sync(alt_title)
        if page is not None:
            return page

    # Search path: find best match
    results = search_sync(display, limit=3)
    if not results:
        logger.debug("resolve_page_sync miss | topic=%s no_results", topic_name)
        return None

    # Pick best result and fetch the full page
    best = results[0]
    logger.debug("resolve_page_sync search_match | topic=%s -> %s (pageid=%d)",
                 topic_name, best.title, best.pageid)

    return get_page_sync(best.title)


# ─────────────────────────────────────────────────────────────────────
# Transformation: WikipediaPage → ResearchResult
# ─────────────────────────────────────────────────────────────────────

def _extract_key_concepts(page: WikipediaPage) -> List[dict]:
    """Extract key concepts from H2 section headings with their text content.

    Uses top-level sections (toclevel=1) as concept names and their
    fetched text as descriptions. Returns up to 6 concepts.
    """
    skip_titles = {
        "see also", "references", "notes",
        "further reading", "external links",
        "bibliography", "footnotes", "citation",
    }
    # Also skip use-case section titles to avoid overlap
    skip_titles.update(t.lower() for t in _USE_CASE_SECTION_TITLES)

    concepts = []
    for s in page.sections:
        if s.get("toclevel") != 1:
            continue
        line = s.get("line", "").strip()
        if not line:
            continue
        if line.lower() in skip_titles:
            continue

        # Use actual section text if available, otherwise fall back to generic
        section_text = page.section_texts.get(s.get("index", ""), "").strip()
        if section_text:
            # Truncate to ~300 chars for card display
            description = section_text[:300]
            if len(section_text) > 300:
                description += "..."
        else:
            description = f"A key aspect of {page.title} covered in the Wikipedia article."

        concepts.append({
            "name": line,
            "description": description,
        })
        if len(concepts) >= 6:
            break
    return concepts


def _extract_use_cases(page: WikipediaPage) -> List[dict]:
    """Try to find an 'Applications' or 'Uses' section.

    Falls back to empty list — use cases are the weakest Wikipedia mapping.
    """
    for s in page.sections:
        line = s.get("line", "").strip()
        if line.lower() in (t.lower() for t in _USE_CASE_SECTION_TITLES):
            # Found an applications section
            return [{
                "name": f"{page.title} applications",
                "description": f"The Wikipedia article includes a '{line}' section "
                               f"detailing practical uses of {page.title}.",
            }]
    return []


def page_to_research_result(page: WikipediaPage) -> ResearchResult:
    """Convert a WikipediaPage into a ResearchResult.

    Maps:
      - summary      → extract first paragraph
      - overview     → lead section
      - key_concepts → H2 section headings
      - use_cases    → "Applications" section (best-effort)
      - parent_topics→ filtered categories
      - child_topics → filtered linkshere
      - related_topics → filtered links

    Returns a ResearchResult compatible with build_knowledge_map().
    """
    # Parent topics from categories (take top 3 most relevant)
    parent_topics = [
        {"name": _slugify(cat), "description": f"Broader field: {cat}"}
        for cat in page.categories[:3]
    ]

    # Child topics from linkshere (top 3)
    child_topics = [
        {"name": _slugify(link), "description": f"Sub-topic that references {page.title}"}
        for link in page.linkshere[:3]
    ]

    # Related topics from links (top 3, deduplicate against children)
    child_names = {c["name"] for c in child_topics}
    related_topics = [
        {"name": _slugify(link), "description": f"Related article on Wikipedia"}
        for link in page.links
        if _slugify(link) not in child_names
    ][:3]

    return ResearchResult(
        summary=page.summary or page.description or f"A Wikipedia article about {page.title}.",
        overview=page.overview or f"See the Wikipedia article for {page.title}.",
        key_concepts=_extract_key_concepts(page),
        use_cases=_extract_use_cases(page),
        parent_topics=parent_topics,
        child_topics=child_topics,
        related_topics=related_topics,
    )


def page_to_markdown(page: WikipediaPage) -> str:
    """Convert a WikipediaPage into structured markdown.

    Produces a document with ## Overview, ## Key Concepts, and
    ## Use Cases sections (if available). This mirrors the output
    format of generate_library_content().
    """
    display = page.title.replace("_", " ").strip()
    lines = [f"# {display}", ""]

    # Summary
    if page.summary:
        lines.append(f"> {page.summary}")
        lines.append("")

    # Overview (lead section)
    if page.overview:
        lines.append("## Overview")
        lines.append("")
        lines.append(page.overview)
        lines.append("")

    # Key Concepts (from H2 sections with actual text)
    concepts = _extract_key_concepts(page)
    if concepts:
        lines.append("## Key Concepts")
        lines.append("")
        for kc in concepts:
            desc = kc['description'].replace('\n', ' ').strip()
            lines.append(f"- **{kc['name']}**: {desc}")
        lines.append("")

    # Use cases (best-effort)
    use_cases = _extract_use_cases(page)
    if use_cases:
        lines.append("## Use Cases")
        lines.append("")
        for uc in use_cases:
            lines.append(f"- **{uc['name']}**: {uc['description']}")
        lines.append("")

    # Attribution
    lines.append("## Source")
    lines.append("")
    lines.append(f"*Sourced from Wikipedia — [{display}](https://en.wikipedia.org/wiki/{page.title.replace(' ', '_')})*")

    return "\n".join(lines)


def page_to_taxonomy(page: WikipediaPage) -> dict:
    """Convert a WikipediaPage into a taxonomy dict.

    Returns the same structure as generate_topic_taxonomy():
      {
        "parent_topics": [{"name": str, "description": str}, ...],
        "child_topics": [{"name": str, "description": str}, ...],
        "related_topics": [{"name": str, "description": str}, ...],
      }
    """
    parent_topics = [
        {"name": _slugify(cat), "description": f"Wikipedia category: {cat}"}
        for cat in page.categories[:3]
    ]
    child_topics = [
        {"name": _slugify(link), "description": f"Links to {page.title} on Wikipedia"}
        for link in page.linkshere[:3]
    ]
    child_names = {c["name"] for c in child_topics}
    related_topics = [
        {"name": _slugify(link), "description": "Related Wikipedia article"}
        for link in page.links
        if _slugify(link) not in child_names
    ][:3]

    return {
        "parent_topics": parent_topics,
        "child_topics": child_topics,
        "related_topics": related_topics,
    }
