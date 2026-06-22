"""
Tests for the Wikipedia service — search, page fetching, caching, and transformations.

Uses mocked httpx.AsyncClient responses to avoid real API calls.
"""

import json
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from app.services.wikipedia_service import (
    WikipediaPage,
    SearchResult,
    search,
    get_page,
    get_section_text,
    get_page_section_texts,
    page_to_research_result,
    page_to_markdown,
    page_to_taxonomy,
    _filter_categories,
    _filter_links,
    _slugify,
    _extract_key_concepts,
    _extract_use_cases,
    clear_cache,
)


# ── Mock Wikipedia API responses ─────────────────────────────

MOCK_SEARCH_RESPONSE = {
    "query": {
        "search": [
            {
                "title": "Quantum computing",
                "pageid": 25220,
                "snippet": "A <span class=\"searchmatch\">quantum</span> computer uses quantum phenomena...",
                "wordcount": 12000,
                "size": 80000,
            },
            {
                "title": "Quantum algorithm",
                "pageid": 12345,
                "snippet": "<span class=\"searchmatch\">Quantum</span> algorithms run on quantum computers...",
                "wordcount": 3000,
                "size": 20000,
            },
        ]
    }
}

MOCK_PAGE_EXTRACT = {
    "batchcomplete": "",
    "query": {
        "pages": {
            "25220": {
                "pageid": 25220,
                "ns": 0,
                "title": "Quantum computing",
                "extract": (
                    "A quantum computer uses quantum phenomena like superposition "
                    "and entanglement to perform computation.\n\n"
                    "The basic unit of information in quantum computing is the qubit. "
                    "Unlike classical bits, qubits can exist in multiple states simultaneously.\n\n"
                    "Quantum computers are not yet practical for real-world applications. "
                    "Physically engineering high-quality qubits has proven challenging."
                ),
            }
        }
    },
}

MOCK_FULL_TEXT = {
    "batchcomplete": "",
    "query": {
        "pages": {
            "25220": {
                "pageid": 25220,
                "title": "Quantum computing",
                "extract": (
                    "A quantum computer uses quantum phenomena like superposition "
                    "and entanglement to perform computation.\n\n"
                    "The basic unit of information in quantum computing is the qubit.\n\n"
                    "== History ==\n"
                    "Quantum computing began in the 1980s...\n\n"
                    "== Quantum information processing ==\n"
                    "Quantum information theory describes how...\n\n"
                    "== Applications ==\n"
                    "Quantum computers have potential applications in cryptography..."
                ),
            }
        }
    },
}

MOCK_CATEGORIES = {
    "query": {
        "pages": {
            "25220": {
                "categories": [
                    {"title": "Category:Classes of computers"},
                    {"title": "Category:Models of computation"},
                    {"title": "Category:Information theory"},
                    {"title": "Category:All Wikipedia articles written in American English"},
                    {"title": "Category:Articles with short description"},
                    {"title": "Category:CS1 maint: deprecated archival service"},
                ],
            }
        }
    },
}

MOCK_LINKS = {
    "query": {
        "pages": {
            "25220": {
                "links": [
                    {"title": "Qubit"},
                    {"title": "Quantum supremacy"},
                    {"title": "Shor's algorithm"},
                    {"title": "Quantum entanglement"},
                    {"title": "List of quantum processors"},
                    {"title": "Timeline of quantum computing and communication"},
                ],
            }
        }
    },
}

MOCK_LINKSHERE = {
    "query": {
        "pages": {
            "25220": {
                "linkshere": [
                    {"title": "Quantum algorithm"},
                    {"title": "Superconducting quantum computing"},
                    {"title": "Trapped ion quantum computer"},
                ],
            }
        }
    },
}

MOCK_SECTIONS = {
    "parse": {
        "title": "Quantum computing",
        "pageid": 25220,
        "sections": [
            {"toclevel": 1, "line": "History", "index": "1", "number": "1"},
            {"toclevel": 1, "line": "Quantum information processing", "index": "2", "number": "2"},
            {"toclevel": 2, "line": "Quantum information", "index": "3", "number": "2.1"},
            {"toclevel": 2, "line": "Unitary operators", "index": "4", "number": "2.2"},
            {"toclevel": 1, "line": "Applications", "index": "5", "number": "3"},
            {"toclevel": 1, "line": "See also", "index": "6", "number": "4"},
            {"toclevel": 1, "line": "References", "index": "7", "number": "5"},
        ],
    }
}

MOCK_IMAGE = {
    "query": {
        "pages": {
            "25220": {
                "pageimage": "IBM_Quantum_Computer.jpg",
                "thumbnail": {
                    "source": "https://upload.wikimedia.org/wikipedia/commons/thumb/example.jpg/200px-example.jpg",
                    "width": 200,
                    "height": 150,
                },
            }
        }
    },
}

MOCK_SECTION_TEXT = {
    "parse": {
        "title": "Quantum computing",
        "text": {
            "*": "<div><p>The history of quantum computing dates back to the 1980s when Richard Feynman proposed the idea of a quantum computer.</p></div>"
        }
    }
}


# ── Helper: create a mock response context ───────────────────

class MockResponse:
    def __init__(self, json_data, status_code=200):
        self._json_data = json_data
        self.status_code = status_code

    def json(self):
        return self._json_data

    def raise_for_status(self):
        if self.status_code >= 400:
            from httpx import HTTPStatusError
            raise HTTPStatusError("error", response=self)


def _mock_async_client_get(url, **kwargs):
    """Determine which mock response to return based on params."""
    params = kwargs.get("params", {})

    # Search
    if params.get("list") == "search":
        return MockResponse(MOCK_SEARCH_RESPONSE)

    # Parse + sections
    if params.get("action") == "parse":
        if params.get("prop") == "sections":
            return MockResponse(MOCK_SECTIONS)
        if params.get("prop") == "text":
            return MockResponse(MOCK_SECTION_TEXT)

    # Query
    if params.get("action") == "query":
        props = params.get("prop", "")

        # Page images
        if "pageimages" in props:
            return MockResponse(MOCK_IMAGE)

        # Categories
        if "categories" in props:
            return MockResponse(MOCK_CATEGORIES)

        # Links
        if props == "links":
            return MockResponse(MOCK_LINKS)

        # Linkshere
        if "linkshere" in props:
            return MockResponse(MOCK_LINKSHERE)

        # Extracts — check exintro
        if "extracts" in props:
            if params.get("exintro") == "1":
                return MockResponse(MOCK_PAGE_EXTRACT)
            return MockResponse(MOCK_FULL_TEXT)

    # Default: empty page
    return MockResponse({"query": {"pages": {"-1": {"missing": True, "title": "Unknown"}}}})


# ── Unit tests: pure functions ────────────────────────────────

class TestFilterCategories:
    def test_filters_maintenance_categories(self):
        raw = [
            "Category:Classes of computers",
            "Category:All Wikipedia articles written in American English",
            "Category:Models of computation",
            "Category:Articles with short description",
            "Category:CS1 maint: deprecated archival service",
            "Category:Information theory",
        ]
        result = _filter_categories(raw)
        assert "Classes of computers" in result
        assert "Models of computation" in result
        assert "Information theory" in result
        assert "All Wikipedia articles written in American English" not in result
        assert "Articles with short description" not in result
        assert "CS1 maint: deprecated archival service" not in result

    def test_handles_no_category_prefix(self):
        result = _filter_categories(["Category:Physics", "Plain text"])
        assert "Physics" in result
        assert "Plain text" in result


class TestFilterLinks:
    def test_filters_list_and_disambiguation_links(self):
        raw = [
            "Qubit",
            "List of quantum processors",
            "Quantum computing (disambiguation)",
            "Shor's algorithm",
        ]
        result = _filter_links(raw)
        assert "Qubit" in result
        assert "Shor's algorithm" in result
        assert "List of quantum processors" not in result
        assert "Quantum computing (disambiguation)" not in result

    def test_handles_empty_list(self):
        assert _filter_links([]) == []


class TestSlugify:
    def test_basic_slug(self):
        assert _slugify("Quantum computing") == "quantum-computing"

    def test_handles_punctuation(self):
        assert _slugify("C++ Programming Language") == "c-programming-language"

    def test_handles_possessives(self):
        assert _slugify("Turing's machine") == "turing-machine"

    def test_handles_parentheses(self):
        assert _slugify("CPU (Central Processing Unit)") == "cpu-central-processing-unit"

    def test_truncates_long_names(self):
        long_name = "a" * 200
        result = _slugify(long_name)
        assert len(result) <= 120

    def test_handles_empty(self):
        assert _slugify("") == ""
        assert _slugify("   ") == ""


# ── Unit tests: concept / use-case extraction ────────────────

class TestExtractKeyConcepts:
    def test_extracts_h2_sections(self):
        page = WikipediaPage(
            title="Quantum computing", pageid=25220,
            summary="", overview="", description="",
            sections=[
                {"toclevel": 1, "line": "History", "index": "1", "number": "1"},
                {"toclevel": 1, "line": "Quantum information processing", "index": "2", "number": "2"},
                {"toclevel": 2, "line": "Quantum information", "index": "3", "number": "2.1"},
                {"toclevel": 1, "line": "Applications", "index": "4", "number": "3"},
                {"toclevel": 1, "line": "See also", "index": "5", "number": "4"},
                {"toclevel": 1, "line": "References", "index": "6", "number": "5"},
            ],
            categories=[], links=[], linkshere=[], full_text="", image_url="",
        )
        concepts = _extract_key_concepts(page)
        names = {c["name"] for c in concepts}
        assert "History" in names
        assert "Quantum information processing" in names
        # H3 sections (toclevel 2) should NOT be included
        assert "Quantum information" not in names
        # Meta sections should be filtered
        assert "See also" not in names
        assert "References" not in names
        # Use-case section titles should be filtered (avoid overlap with use_cases)
        assert "Applications" not in names

    def test_caps_at_6_concepts(self):
        sections = [
            {"toclevel": 1, "line": f"Section {i}", "index": str(i), "number": str(i)}
            for i in range(1, 10)
        ]
        page = WikipediaPage(
            title="Test", pageid=1, summary="", overview="", description="",
            sections=sections,
            categories=[], links=[], linkshere=[], full_text="", image_url="",
        )
        concepts = _extract_key_concepts(page)
        assert len(concepts) == 6

    def test_empty_sections(self):
        page = WikipediaPage(
            title="Test", pageid=1, summary="", overview="", description="",
            sections=[],
            categories=[], links=[], linkshere=[], full_text="", image_url="",
        )
        assert _extract_key_concepts(page) == []


class TestExtractUseCases:
    def test_finds_applications_section(self):
        page = WikipediaPage(
            title="Quantum computing", pageid=25220,
            summary="", overview="", description="",
            sections=[
                {"toclevel": 1, "line": "History", "index": "1", "number": "1"},
                {"toclevel": 1, "line": "Applications", "index": "2", "number": "2"},
            ],
            categories=[], links=[], linkshere=[], full_text="", image_url="",
        )
        result = _extract_use_cases(page)
        assert len(result) == 1
        assert "applications" in result[0]["name"].lower()

    def test_finds_uses_section(self):
        page = WikipediaPage(
            title="Test", pageid=1, summary="", overview="", description="",
            sections=[
                {"toclevel": 1, "line": "Uses", "index": "1", "number": "1"},
            ],
            categories=[], links=[], linkshere=[], full_text="", image_url="",
        )
        result = _extract_use_cases(page)
        assert len(result) == 1

    def test_no_applications_section_returns_empty(self):
        page = WikipediaPage(
            title="Test", pageid=1, summary="", overview="", description="",
            sections=[
                {"toclevel": 1, "line": "History", "index": "1", "number": "1"},
            ],
            categories=[], links=[], linkshere=[], full_text="", image_url="",
        )
        assert _extract_use_cases(page) == []


# ── Transformation tests ─────────────────────────────────────

def _make_mock_page() -> WikipediaPage:
    """Create a realistic-looking WikipediaPage for transformation tests."""
    return WikipediaPage(
        title="Quantum computing",
        pageid=25220,
        summary="A quantum computer uses quantum phenomena to perform computation.",
        overview=(
            "A quantum computer uses quantum phenomena like superposition "
            "and entanglement to perform computation.\n\n"
            "The qubit is the basic unit of quantum information."
        ),
        description="Computer hardware technology that uses quantum mechanics",
        sections=[
            {"toclevel": 1, "line": "History", "index": "1", "number": "1"},
            {"toclevel": 1, "line": "Quantum information processing", "index": "2", "number": "2"},
            {"toclevel": 1, "line": "Applications", "index": "3", "number": "3"},
        ],
        categories=[
            "Classes of computers",
            "Models of computation",
            "Information theory",
            "Quantum information science",
        ],
        links=[
            "Qubit",
            "Quantum supremacy",
            "Shor's algorithm",
            "Quantum entanglement",
        ],
        linkshere=[
            "Quantum algorithm",
            "Superconducting quantum computing",
        ],
        full_text="Full article text...",
        image_url="https://example.com/image.jpg",
    )


class TestPageToResearchResult:
    def test_produces_research_result(self):
        page = _make_mock_page()
        result = page_to_research_result(page)

        assert result.summary == page.summary
        assert result.overview == page.overview
        assert len(result.key_concepts) > 0
        assert len(result.use_cases) > 0
        assert len(result.parent_topics) <= 3
        assert len(result.child_topics) <= 3
        assert len(result.related_topics) <= 3

    def test_parent_topics_are_slugs(self):
        page = _make_mock_page()
        result = page_to_research_result(page)
        for pt in result.parent_topics:
            assert pt["name"] == pt["name"].lower()
            assert " " not in pt["name"]

    def test_child_related_no_overlap(self):
        """Child and related topics should not share the same slugs."""
        page = _make_mock_page()
        result = page_to_research_result(page)
        child_names = {c["name"] for c in result.child_topics}
        related_names = {r["name"] for r in result.related_topics}
        assert child_names.isdisjoint(related_names)


class TestPageToMarkdown:
    def test_produces_structured_markdown(self):
        page = _make_mock_page()
        md = page_to_markdown(page)

        assert md.startswith("# Quantum computing")
        assert "> A quantum computer" in md
        assert "## Overview" in md
        assert "## Key Concepts" in md
        assert "## Use Cases" in md
        assert "## Source" in md

    def test_includes_attribution(self):
        page = _make_mock_page()
        md = page_to_markdown(page)
        assert "## Source" in md
        assert "Sourced from Wikipedia" in md
        assert "https://en.wikipedia.org/wiki/" in md

    def test_handles_minimal_page(self):
        page = WikipediaPage(
            title="Minimal", pageid=1,
            summary="", overview="", description="",
            sections=[], categories=[], links=[],
            linkshere=[], full_text="", image_url="",
        )
        md = page_to_markdown(page)
        assert "# Minimal" in md
        # Should not crash
        assert isinstance(md, str)


class TestPageToTaxonomy:
    def test_produces_expected_structure(self):
        page = _make_mock_page()
        taxonomy = page_to_taxonomy(page)

        assert "parent_topics" in taxonomy
        assert "child_topics" in taxonomy
        assert "related_topics" in taxonomy
        assert isinstance(taxonomy["parent_topics"], list)
        assert isinstance(taxonomy["child_topics"], list)
        assert isinstance(taxonomy["related_topics"], list)

    def test_taxonomy_items_have_name_and_description(self):
        page = _make_mock_page()
        taxonomy = page_to_taxonomy(page)
        for key in ("parent_topics", "child_topics", "related_topics"):
            for item in taxonomy[key]:
                assert "name" in item
                assert "description" in item
                assert item["name"]  # non-empty

    def test_handles_empty_page(self):
        page = WikipediaPage(
            title="Empty", pageid=1, summary="", overview="", description="",
            sections=[], categories=[], links=[], linkshere=[],
            full_text="", image_url="",
        )
        taxonomy = page_to_taxonomy(page)
        assert taxonomy == {
            "parent_topics": [],
            "child_topics": [],
            "related_topics": [],
        }


# ── Helper: mock httpx.AsyncClient for integration tests ─────

def _mock_async_client_factory(response_map=None):
    """Create a mock httpx.AsyncClient that returns predefined responses.

    response_map is a dict mapping param signatures to MockResponse objects.
    If None, uses built-in routing.
    """
    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock()
    mock_client.__aexit__ = AsyncMock()

    async def mock_get(url, **kwargs):
        params = kwargs.get("params", {})
        prop = params.get("prop", "")
        action = params.get("action", "query")
        list_action = params.get("list", "")

        if list_action == "search":
            return MockResponse(MOCK_SEARCH_RESPONSE)
        if action == "parse":
            if params.get("prop") == "sections":
                return MockResponse(MOCK_SECTIONS)
            return MockResponse(MOCK_SECTION_TEXT)
        if "pageimages" in prop:
            return MockResponse(MOCK_IMAGE)
        if "categories" in prop:
            return MockResponse(MOCK_CATEGORIES)
        if prop == "links":
            return MockResponse(MOCK_LINKS)
        if "linkshere" in prop:
            return MockResponse(MOCK_LINKSHERE)
        if "extracts" in prop:
            if params.get("exintro") == "1":
                return MockResponse(MOCK_PAGE_EXTRACT)
            return MockResponse(MOCK_FULL_TEXT)
        return MockResponse({"query": {"pages": {"-1": {"missing": True, "title": "Unknown"}}}})

    mock_client.get = mock_get
    mock_client.__aenter__.return_value = mock_client
    return mock_client


# ── Integration: search() with mocked HTTP ───────────────────

class TestSearch:
    @pytest.mark.asyncio
    async def test_returns_search_results(self):
        clear_cache()
        mock_client = _mock_async_client_factory()

        with patch("httpx.AsyncClient", return_value=mock_client):
            results = await search("quantum computing")

        assert len(results) == 2
        assert results[0].title == "Quantum computing"
        assert results[0].pageid == 25220
        assert isinstance(results[0].snippet, str)
        # HTML should be stripped from snippets
        assert "<span" not in results[0].snippet

    @pytest.mark.asyncio
    async def test_empty_results_on_error(self):
        clear_cache()
        mock_client = _mock_async_client_factory()
        mock_client.get = AsyncMock(side_effect=Exception("Network error"))

        with patch("httpx.AsyncClient", return_value=mock_client):
            results = await search("quantum computing")

        assert results == []

    @pytest.mark.asyncio
    async def test_caches_results(self):
        clear_cache()
        call_count = 0
        mock_client = _mock_async_client_factory()

        orig_get = mock_client.get
        async def counting_get(url, **kwargs):
            nonlocal call_count
            call_count += 1
            return await orig_get(url, **kwargs)
        mock_client.get = counting_get

        with patch("httpx.AsyncClient", return_value=mock_client):
            results1 = await search("quantum computing")
            results2 = await search("quantum computing")

        assert len(results1) == 2
        assert len(results2) == 2
        # Second call should be cached — only 1 API call
        assert call_count == 1


# ── Integration: get_page() with mocked HTTP ─────────────────

class TestGetPage:
    @pytest.mark.asyncio
    async def test_returns_full_wikipedia_page(self):
        clear_cache()
        mock_client = _mock_async_client_factory()

        with patch("httpx.AsyncClient", return_value=mock_client):
            page = await get_page("Quantum computing")

        assert page is not None
        assert page.title == "Quantum computing"
        assert page.pageid == 25220
        assert len(page.summary) > 0
        assert len(page.overview) > 0
        assert len(page.sections) > 0
        assert len(page.categories) > 0
        # Maintenance categories should be filtered out
        for cat in page.categories:
            assert not cat.startswith("All Wikipedia")
            assert not cat.startswith("Articles with")
        assert len(page.links) > 0
        assert len(page.linkshere) > 0
        assert page.image_url != ""

    @pytest.mark.asyncio
    async def test_returns_none_on_missing_page(self):
        clear_cache()
        mock_client = _mock_async_client_factory()

        async def missing_get(url, **kwargs):
            return MockResponse({"query": {"pages": {"-1": {"missing": True, "title": "Nonesuch", "ns": 0}}}})
        mock_client.get = missing_get

        with patch("httpx.AsyncClient", return_value=mock_client):
            page = await get_page("Nonesuch")

        assert page is None

    @pytest.mark.asyncio
    async def test_returns_none_on_http_error(self):
        clear_cache()
        from httpx import HTTPStatusError

        mock_client = _mock_async_client_factory()

        async def error_get(url, **kwargs):
            mock_resp = MagicMock()
            mock_resp.status_code = 404
            raise HTTPStatusError("Not found", response=mock_resp)
        mock_client.get = error_get

        with patch("httpx.AsyncClient", return_value=mock_client):
            page = await get_page("Whatever")

        assert page is None


# ── Integration: get_section_text() ───────────────────────────

class TestGetSectionText:
    @pytest.mark.asyncio
    async def test_returns_plain_text(self):
        clear_cache()
        mock_client = _mock_async_client_factory()

        with patch("httpx.AsyncClient", return_value=mock_client):
            text = await get_section_text("Quantum computing", "1")

        assert len(text) > 0
        assert "Richard Feynman" in text
        # HTML should be stripped
        assert "<div>" not in text
        assert "<p>" not in text

    @pytest.mark.asyncio
    async def test_returns_empty_on_error(self):
        clear_cache()
        mock_client = _mock_async_client_factory()
        mock_client.get = AsyncMock(side_effect=Exception("Network error"))

        with patch("httpx.AsyncClient", return_value=mock_client):
            text = await get_section_text("Quantum computing", "1")

        assert text == ""


# ── Integration: get_page_section_texts() ─────────────────────

class TestGetPageSectionTexts:
    @pytest.mark.asyncio
    async def test_fetches_multiple_sections(self):
        clear_cache()
        mock_client = _mock_async_client_factory()

        with patch("httpx.AsyncClient", return_value=mock_client):
            texts = await get_page_section_texts("Test", ["1", "2", "3"])

        assert set(texts.keys()) == {"1", "2", "3"}
        # Each section returns text from MOCK_SECTION_TEXT
        assert len(texts["1"]) > 0

    @pytest.mark.asyncio
    async def test_handles_empty_list(self):
        texts = await get_page_section_texts("Test", [])
        assert texts == {}


# ── Integration: sync wrappers ────────────────────────────────

class TestSyncWrappers:
    def test_search_sync_returns_results(self):
        from app.services.wikipedia_service import search_sync
        clear_cache()
        mock_client = _mock_async_client_factory()

        with patch("httpx.AsyncClient", return_value=mock_client):
            results = search_sync("quantum computing")

        assert len(results) == 2
        assert results[0].title == "Quantum computing"

    def test_get_page_sync_returns_page(self):
        from app.services.wikipedia_service import get_page_sync
        clear_cache()
        mock_client = _mock_async_client_factory()

        with patch("httpx.AsyncClient", return_value=mock_client):
            page = get_page_sync("Quantum computing")

        assert page is not None
        assert page.title == "Quantum computing"
        assert len(page.categories) > 0

    def test_resolve_page_sync_exact_match(self):
        from app.services.wikipedia_service import resolve_page_sync
        clear_cache()
        mock_client = _mock_async_client_factory()

        with patch("httpx.AsyncClient", return_value=mock_client):
            page = resolve_page_sync("Quantum computing")

        assert page is not None
        assert page.title == "Quantum computing"

    def test_resolve_page_sync_falls_back_to_search(self):
        from app.services.wikipedia_service import resolve_page_sync
        clear_cache()
        mock_client = _mock_async_client_factory()

        call_count = {"get": 0, "search": 0}
        known_titles = {"Quantum computing", "Quantum Computing", "Quantum_computing"}

        orig_get = mock_client.get
        async def get_with_routing(url, **kwargs):
            call_count["get"] += 1
            params = kwargs.get("params", {})
            prop = params.get("prop", "")
            action = params.get("action", "query")
            list_action = params.get("list", "")
            titles = params.get("titles", "")

            # Track searches
            if list_action == "search":
                call_count["search"] += 1
                return MockResponse(MOCK_SEARCH_RESPONSE)

            # Return "missing" for unknown titles, real data for known ones
            if "titles" in params and titles not in known_titles:
                return MockResponse({"query": {"pages": {"-1": {"missing": True, "title": titles}}}})

            # Route normally for known titles
            if "extracts" in prop:
                if params.get("exintro") == "1":
                    return MockResponse(MOCK_PAGE_EXTRACT)
                return MockResponse(MOCK_FULL_TEXT)
            if "categories" in prop:
                return MockResponse(MOCK_CATEGORIES)
            if prop == "links":
                return MockResponse(MOCK_LINKS)
            if "linkshere" in prop:
                return MockResponse(MOCK_LINKSHERE)
            if action == "parse" and params.get("prop") == "sections":
                return MockResponse(MOCK_SECTIONS)
            if "pageimages" in prop:
                return MockResponse(MOCK_IMAGE)
            return MockResponse({"query": {"pages": {}}})

        mock_client.get = get_with_routing

        with patch("httpx.AsyncClient", return_value=mock_client):
            page = resolve_page_sync("obscure topic name")

        assert page is not None
        assert page.title == "Quantum computing"
        assert call_count["search"] >= 1
