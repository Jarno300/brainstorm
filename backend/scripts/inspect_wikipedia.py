"""
inspect_wikipedia.py — Call Wikipedia Action API endpoints for a given topic
and pretty-print the raw JSON responses.

Usage:
    python scripts/inspect_wikipedia.py "Quantum computing"
    python scripts/inspect_wikipedia.py "Machine learning" --output ml_dump.json

This is a development utility to inspect Wikipedia API response shapes.
No app dependencies — uses httpx and asyncio directly.
"""

import argparse
import asyncio
import json
import sys
from pathlib import Path

# Fix Unicode output on Windows consoles
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import httpx

# ── Configuration ──────────────────────────────────────────────

WIKIPEDIA_BASE_URL = "https://en.wikipedia.org/w/api.php"
WIKIPEDIA_USER_AGENT = "Brainstorm/1.0 (https://github.com/brainstorm; knowledge-research-tool)"
TIMEOUT = 20  # seconds

ENDPOINTS = {
    "search": {
        "description": "Search results for topic disambiguation",
        "params": {
            "action": "query",
            "list": "search",
            "srsearch": None,        # filled at call time
            "srlimit": "5",
        },
    },
    "intro_extract": {
        "description": "Lead section intro extract (plain text, intro only)",
        "params": {
            "action": "query",
            "prop": "extracts",
            "exintro": "1",
            "explaintext": "1",
            "titles": None,
        },
    },
    "full_extract": {
        "description": "Full article extract (plain text, whole page)",
        "params": {
            "action": "query",
            "prop": "extracts",
            "explaintext": "1",
            "titles": None,
        },
    },
    "categories": {
        "description": "Article categories (top 30)",
        "params": {
            "action": "query",
            "prop": "categories",
            "titles": None,
            "cllimit": "30",
        },
    },
    "links": {
        "description": "Outgoing page links — related topics (top 50, namespace 0)",
        "params": {
            "action": "query",
            "prop": "links",
            "titles": None,
            "pllimit": "50",
            "plnamespace": "0",
        },
    },
    "linkshere": {
        "description": "Incoming links — pages that link to this one (top 50)",
        "params": {
            "action": "query",
            "prop": "linkshere",
            "titles": None,
            "lhlimit": "50",
            "lhnamespace": "0",
        },
    },
    "sections": {
        "description": "Table of contents / section headings via parse API",
        "params": {
            "action": "parse",
            "page": None,
            "prop": "sections",
        },
    },
    "pageimages": {
        "description": "Page thumbnail (200px)",
        "params": {
            "action": "query",
            "prop": "pageimages",
            "titles": None,
            "pithumbsize": "200",
        },
    },
}

# HACK: pageinfo and iwlinks aren't available in our client; replaced
# with links (namespace 0 only) which returns the same intent.

# ── Helpers ────────────────────────────────────────────────────

def truncate_text(text: str, max_chars: int = 2000) -> str:
    """Truncate text with a note if it exceeds max_chars."""
    if len(text) > max_chars:
        return text[:max_chars] + f"\n\n... [truncated from {len(text):,} chars]"
    return text


async def fetch_endpoint(
    client: httpx.AsyncClient,
    name: str,
    params: dict,
    display_title: str,
) -> tuple[str, dict, str]:
    """Fetch a single Wikipedia API endpoint.

    Returns (endpoint_name, json_data, error_string).
    error_string is empty on success.
    """
    print(f"  -> {name} ({ENDPOINTS[name]['description']}) ...", end=" ", flush=True)
    try:
        response = await client.get(
            WIKIPEDIA_BASE_URL,
            params={**params, "format": "json"},
            headers={
                "User-Agent": WIKIPEDIA_USER_AGENT,
                "Accept": "application/json",
                "Accept-Encoding": "identity",
            },
            timeout=TIMEOUT,
        )
        response.raise_for_status()
        data = response.json()
        print("OK")
        return name, data, ""
    except Exception as e:
        print(f"FAIL ({e})")
        return name, {}, str(e)


async def inspect_topic(topic: str) -> dict:
    """Fetch all Wikipedia endpoints for a topic and return the combined results."""
    results = {}

    async with httpx.AsyncClient() as client:
        # Phase 1: Search for the topic to get the canonical title
        print(f"\n{'='*60}")
        print(f"Topic: {topic}")
        print(f"{'='*60}\n")

        search_params = dict(ENDPOINTS["search"]["params"])
        search_params["srsearch"] = topic
        _, search_data, err = await fetch_endpoint(client, "search", search_params, topic)
        results["search"] = {"error": err, "data": search_data} if err else search_data

        if err:
            print(f"\nERROR: Search failed — {err}")
            return results

        # Extract canonical title from search
        search_hits = search_data.get("query", {}).get("search", [])
        if not search_hits:
            print("\nNo search results found.")
            return results

        canonical_title = search_hits[0]["title"]
        print(f"\n  Canonical title: {canonical_title}")
        print(f"  Match confidence: {search_hits[0].get('wordcount', '?')} words, "
              f"pageid={search_hits[0].get('pageid', '?')}\n")

        # Phase 2: Fetch page-level endpoints in parallel
        page_endpoints = {k: v for k, v in ENDPOINTS.items() if k != "search"}
        page_params = {
            name: {**info["params"], "titles": canonical_title}
            if "titles" in info["params"]
            else {**info["params"], "page": canonical_title}
            for name, info in page_endpoints.items()
        }

        tasks = [
            fetch_endpoint(client, name, page_params[name], canonical_title)
            for name in page_endpoints
        ]
        raw_results = await asyncio.gather(*tasks)

        for name, data, err in raw_results:
            if err:
                results[name] = {"error": err}
            else:
                results[name] = data

    return results


def print_results(results: dict):
    """Pretty-print the inspection results to stdout."""
    print(f"\n{'='*60}")
    print("RESULTS SUMMARY")
    print(f"{'='*60}")

    for endpoint_name in ENDPOINTS:
        print(f"\n{'─'*60}")
        print(f"  {endpoint_name}")
        print(f"  {ENDPOINTS[endpoint_name]['description']}")
        print(f"{'─'*60}")

        data = results.get(endpoint_name, {})
        if isinstance(data, dict) and "error" in data and "data" not in data:
            print(f"\n  ERROR: {data['error']}")
            continue

        # Pretty-print relevant parts of each endpoint
        if endpoint_name == "search":
            hits = data.get("query", {}).get("search", [])
            print(f"\n  Total hits: {len(hits)}")
            for i, hit in enumerate(hits):
                print(f"\n  [{i+1}] {hit.get('title', '?')}")
                print(f"      pageid={hit.get('pageid')}, words={hit.get('wordcount')}")
                snippet = hit.get("snippet", "")
                # Strip HTML tags from snippet
                import re
                snippet = re.sub(r"<[^>]+>", "", snippet).strip()
                print(f"      snippet: {snippet[:200]}...")

        elif endpoint_name == "intro_extract":
            pages = data.get("query", {}).get("pages", {})
            for pid, page in pages.items():
                print(f"\n  pageid={page.get('pageid')}, title={page.get('title')}")
                if page.get("missing"):
                    print("  → PAGE MISSING")
                    continue
                extract = page.get("extract", "")
                words = len(extract.split()) if extract else 0
                print(f"  words={words}")
                print(f"  extract preview:\n{truncate_text(extract, 800)}")

        elif endpoint_name == "full_extract":
            pages = data.get("query", {}).get("pages", {})
            for pid, page in pages.items():
                extract = page.get("extract", "")
                words = len(extract.split()) if extract else 0
                chars = len(extract)
                print(f"\n  pageid={page.get('pageid')}")
                print(f"  total words={words:,}, chars={chars:,}")
                # Show first and last 400 chars
                print(f"  first 400 chars:\n{extract[:400]}")
                if chars > 400:
                    print(f"\n  ... (skipping middle) ...")
                    print(f"\n  last 400 chars:\n{extract[-400:]}")

        elif endpoint_name == "categories":
            pages = data.get("query", {}).get("pages", {})
            for pid, page in pages.items():
                cats = page.get("categories", [])
                print(f"\n  Total categories: {len(cats)}")
                for c in cats[:30]:
                    print(f"    {c.get('title', '?')}")

        elif endpoint_name in ("links", "linkshere"):
            pages = data.get("query", {}).get("pages", {})
            key = "links" if endpoint_name == "links" else "linkshere"
            for pid, page in pages.items():
                items = page.get(key, [])
                print(f"\n  Total {endpoint_name}: {len(items)}")
                for item in items[:20]:
                    print(f"    {item.get('title', '?')}")
                if len(items) > 20:
                    print(f"    ... and {len(items) - 20} more")

        elif endpoint_name == "sections":
            secs = data.get("parse", {}).get("sections", [])
            print(f"\n  Total sections: {len(secs)}")
            for s in secs[:25]:
                indent = "  " * (int(s.get("toclevel", 1)) - 1)
                print(f"    {indent}[{s.get('number', '?')}] {s.get('line', '?')} "
                      f"(index={s.get('index')}, toclevel={s.get('toclevel')})")
            if len(secs) > 25:
                print(f"    ... and {len(secs) - 25} more sections")

        elif endpoint_name == "pageimages":
            pages = data.get("query", {}).get("pages", {})
            for pid, page in pages.items():
                thumb = page.get("thumbnail", {})
                img = page.get("pageimage", "")
                if thumb:
                    print(f"\n  thumbnail: {thumb.get('source', '?')}")
                    print(f"  dimensions: {thumb.get('width')}x{thumb.get('height')}")
                elif img:
                    print(f"\n  pageimage: {img} (no thumbnail available)")
                else:
                    print(f"\n  No image available")

    print(f"\n{'='*60}")


# ── Main ──────────────────────────────────────────────────────

async def main():
    parser = argparse.ArgumentParser(
        description="Inspect Wikipedia Action API responses for a given topic"
    )
    parser.add_argument(
        "topic",
        nargs="?",
        default="Quantum computing",
        help="Topic to look up on Wikipedia (default: 'Quantum computing')",
    )
    parser.add_argument(
        "--output", "-o",
        type=Path,
        default=None,
        help="Write full JSON dump to this file",
    )
    parser.add_argument(
        "--all-hits",
        action="store_true",
        default=False,
        help="Include all search hits (not just top result)",
    )
    args = parser.parse_args()

    topic = args.topic
    results = await inspect_topic(topic)

    # Pretty-print to stdout
    print_results(results)

    # Write raw JSON dump if requested
    output_path = args.output or Path(f"wikipedia_dump_{topic.lower().replace(' ', '_')[:50]}.json")
    dump_data = {
        "topic": topic,
        "endpoints": results,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(dump_data, f, indent=2, ensure_ascii=False)
    print(f"\nRaw JSON dump written to: {output_path.resolve()}")

    # Quick stats
    search_hits = results.get("search", {}).get("query", {}).get("search", [])
    print(f"\nQuick stats:")
    print(f"  Search hits: {len(search_hits)}")
    if search_hits:
        print(f"  Best match: {search_hits[0]['title']}")
    for name in ("categories", "links", "linkshere"):
        data = results.get(name, {})
        pages = data.get("query", {}).get("pages", {})
        key = "links" if name == "links" else "linkshere" if name == "linkshere" else "categories"
        for _, page in pages.items():
            print(f"  {name}: {len(page.get(key, []))} items")


if __name__ == "__main__":
    asyncio.run(main())
