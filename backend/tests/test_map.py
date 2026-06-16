"""Tests for map API endpoints — blank cards, outline, connection exploration."""

import uuid
import pytest
from app.services.map_suggestion_service import _extract_topic_bullets_from_section


# ── Unit: Suggestion name truncation ──────────────────────────

class TestSuggestionNameTruncation:

    def test_truncates_long_llm_output(self):
        """LLM may produce a full sentence as a bullet — name must fit 255 chars."""
        source = (
            "## Related Topics\n"
            "- **classical-bit**:-the-classical-bit-is-a-binary-unit-(0-or-1)-that-"
            "underlies-all-traditional-computing.-while-a-qubit-can-represent-both-"
            "states-simultaneously,-a-classical-bit-is-deterministic-and-robust,-"
            "making-it-suitable-for-everyday-tasks-but-limited-for-quantum-speed-problems.\n"
        )
        items = _extract_topic_bullets_from_section(source, "Related Topics")
        assert len(items) == 1
        # Name must be short enough to slugify and fit in 255 chars
        assert len(items[0]["name"]) <= 120
        # Markdown formatting should be stripped
        assert "**" not in items[0]["name"]

    def test_normal_bullet_format(self):
        """Standard format: - slug-name - description."""
        source = (
            "## Related Topics\n"
            "- quantum-entanglement - A fundamental quantum phenomenon\n"
            "- error-correction - Essential for practical quantum computing\n"
        )
        items = _extract_topic_bullets_from_section(source, "Related Topics")
        assert len(items) == 2
        assert items[0]["name"] == "quantum-entanglement"
        assert items[0]["description"] == "A fundamental quantum phenomenon"
        assert items[1]["name"] == "error-correction"

    def test_bullet_with_asterisks(self):
        """Bullets using * instead of -."""
        source = (
            "## Related Topics\n"
            "* shors-algorithm - Famous quantum algorithm\n"
        )
        items = _extract_topic_bullets_from_section(source, "Related Topics")
        assert len(items) == 1
        assert items[0]["name"] == "shors-algorithm"

    def test_numbered_list(self):
        """Numbered bullets."""
        source = (
            "## Related Topics\n"
            "1. grovers-algorithm - Quantum search\n"
        )
        items = _extract_topic_bullets_from_section(source, "Related Topics")
        assert len(items) == 1
        assert items[0]["name"] == "grovers-algorithm"

    def test_no_section_returns_empty(self):
        """Missing section heading."""
        source = "## Other Section\n- something"
        items = _extract_topic_bullets_from_section(source, "Related Topics")
        assert items == []

    def test_empty_section_returns_empty(self):
        """Empty section."""
        source = "## Related Topics\n\n## Next Section"
        items = _extract_topic_bullets_from_section(source, "Related Topics")
        assert items == []


# ── Integration: Topic CRUD with outline (no LLM required) ────

class TestBlankTopicCreation:

    def test_create_blank_topic_no_auto_generate(self, client, auth_headers, brainstorm_factory):
        """Creating a topic with auto_generate=False skips LLM and library generation."""
        b = brainstorm_factory(title="Research")

        resp = client.post(
            f"/api/v1/map/{b.id}/topics",
            json={"name": "My Blank Topic", "auto_generate": False},
            headers=auth_headers,
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "my-blank-topic"
        assert data["is_proposition"] == False
        assert data["library_path"] == ""
        assert data["outline"] is None

    def test_create_blank_topic_with_outline(self, client, auth_headers, brainstorm_factory):
        """Outline is stored on creation."""
        b = brainstorm_factory(title="Research")

        resp = client.post(
            f"/api/v1/map/{b.id}/topics",
            json={
                "name": "Structured Topic",
                "auto_generate": False,
                "outline": [{"title": "History"}, {"title": "Key Concepts"}],
            },
            headers=auth_headers,
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["outline"] == [{"title": "History"}, {"title": "Key Concepts"}]
        # No library should have been auto-generated
        assert data["library_path"] == ""

    def test_create_blank_topic_duplicate_name(self, client, auth_headers, brainstorm_factory):
        """Duplicate topic name returns 409."""
        b = brainstorm_factory(title="Research")

        client.post(
            f"/api/v1/map/{b.id}/topics",
            json={"name": "Unique Topic", "auto_generate": False},
            headers=auth_headers,
        )
        resp = client.post(
            f"/api/v1/map/{b.id}/topics",
            json={"name": "Unique Topic", "auto_generate": False},
            headers=auth_headers,
        )
        assert resp.status_code == 409

    def test_create_blank_topic_appears_in_map(self, client, auth_headers, brainstorm_factory):
        """Blank topic appears in map GET response with outline."""
        b = brainstorm_factory(title="Research")

        client.post(
            f"/api/v1/map/{b.id}/topics",
            json={
                "name": "Map Topic",
                "auto_generate": False,
                "outline": [{"title": "Section A"}],
            },
            headers=auth_headers,
        )

        resp = client.get(f"/api/v1/map/{b.id}", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        topics = data["topics"]
        assert len(topics) == 1
        assert topics[0]["name"] == "map-topic"
        assert topics[0]["outline"] == [{"title": "Section A"}]

    def test_create_blank_topic_requires_auth(self, client, brainstorm_factory):
        b = brainstorm_factory(title="Research")
        resp = client.post(
            f"/api/v1/map/{b.id}/topics",
            json={"name": "No Auth", "auto_generate": False},
        )
        assert resp.status_code == 401


class TestOutlineUpdate:

    def test_update_outline_on_topic(self, client, auth_headers, brainstorm_factory):
        """Patching outline on an existing topic works."""
        b = brainstorm_factory(title="Research")

        # Create a blank topic first
        create_resp = client.post(
            f"/api/v1/map/{b.id}/topics",
            json={"name": "Outline Test", "auto_generate": False},
            headers=auth_headers,
        )
        topic_id = create_resp.json()["id"]

        # Update outline
        resp = client.patch(
            f"/api/v1/map/{b.id}/topics/{topic_id}",
            json={"outline": [{"title": "Introduction"}, {"title": "Methods"}]},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["outline"] == [{"title": "Introduction"}, {"title": "Methods"}]

    def test_clear_outline(self, client, auth_headers, brainstorm_factory):
        """Setting outline to empty list clears it."""
        b = brainstorm_factory(title="Research")

        create_resp = client.post(
            f"/api/v1/map/{b.id}/topics",
            json={
                "name": "Clear Test",
                "auto_generate": False,
                "outline": [{"title": "Keep Me"}],
            },
            headers=auth_headers,
        )
        topic_id = create_resp.json()["id"]

        # Clear the outline
        resp = client.patch(
            f"/api/v1/map/{b.id}/topics/{topic_id}",
            json={"outline": []},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["outline"] == []

    def test_update_name_and_outline_together(self, client, auth_headers, brainstorm_factory):
        """Partial update: name + outline in one call."""
        b = brainstorm_factory(title="Research")

        create_resp = client.post(
            f"/api/v1/map/{b.id}/topics",
            json={"name": "Old Name", "auto_generate": False},
            headers=auth_headers,
        )
        topic_id = create_resp.json()["id"]

        resp = client.patch(
            f"/api/v1/map/{b.id}/topics/{topic_id}",
            json={"name": "New Name", "outline": [{"title": "Section 1"}]},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "new-name"
        assert data["outline"] == [{"title": "Section 1"}]


class TestGenerateValidation:

    def test_generate_without_outline_requires_real_llm(self, client, auth_headers, brainstorm_factory):
        """Generate on a topic with no outline — skips the 400, tries LLM.
        Since API keys are empty in test, this will fail at the LLM call (500 or 503).
        """
        b = brainstorm_factory(title="Research", model="ollama/llama3.2:1b")

        create_resp = client.post(
            f"/api/v1/map/{b.id}/topics",
            json={"name": "Generate Test", "auto_generate": False},
            headers=auth_headers,
        )
        topic_id = create_resp.json()["id"]

        # With no outline, should NOT return 400 — should attempt generation
        resp = client.post(
            f"/api/v1/map/{b.id}/topics/{topic_id}/generate",
            headers=auth_headers,
        )
        # Not a 400 — either succeeds or fails at LLM level (500/503)
        assert resp.status_code != 400

    def test_generate_on_nonexistent_topic(self, client, auth_headers, brainstorm_factory):
        """Generate on a fake topic returns 404."""
        b = brainstorm_factory(title="Research")
        fake_id = str(uuid.uuid4())
        resp = client.post(
            f"/api/v1/map/{b.id}/topics/{fake_id}/generate",
            headers=auth_headers,
        )
        assert resp.status_code == 404


class TestExploreConnection:

    def test_explore_connection_nonexistent_source(self, client, auth_headers, brainstorm_factory):
        """Explore with a fake source topic returns 404."""
        b = brainstorm_factory(title="Research")

        # Create one real topic
        create_resp = client.post(
            f"/api/v1/map/{b.id}/topics",
            json={"name": "Real Topic", "auto_generate": False},
            headers=auth_headers,
        )
        real_id = create_resp.json()["id"]

        resp = client.post(
            f"/api/v1/map/{b.id}/explore-connection",
            json={
                "source_topic_id": str(uuid.uuid4()),
                "target_topic_id": real_id,
                "position_x": 200.0,
                "position_y": 150.0,
            },
            headers=auth_headers,
        )
        assert resp.status_code == 404

    def test_explore_connection_requires_auth(self, client, brainstorm_factory):
        b = brainstorm_factory(title="Research")
        resp = client.post(
            f"/api/v1/map/{b.id}/explore-connection",
            json={
                "source_topic_id": str(uuid.uuid4()),
                "target_topic_id": str(uuid.uuid4()),
                "position_x": 0.0,
                "position_y": 0.0,
            },
        )
        assert resp.status_code == 401

    def test_explore_connection_wrong_brainstorm(self, client, auth_headers, brainstorm_factory):
        """Source topic belongs to a different brainstorm."""
        b1 = brainstorm_factory(title="Brainstorm 1")
        b2 = brainstorm_factory(title="Brainstorm 2")

        # Create topic in b2
        create_resp = client.post(
            f"/api/v1/map/{b2.id}/topics",
            json={"name": "Topic in B2", "auto_generate": False},
            headers=auth_headers,
        )
        b2_topic_id = create_resp.json()["id"]

        # Create topic in b1
        create_resp2 = client.post(
            f"/api/v1/map/{b1.id}/topics",
            json={"name": "Topic in B1", "auto_generate": False},
            headers=auth_headers,
        )
        b1_topic_id = create_resp2.json()["id"]

        # Try to explore connection in b1 with b2's topic
        resp = client.post(
            f"/api/v1/map/{b1.id}/explore-connection",
            json={
                "source_topic_id": b1_topic_id,
                "target_topic_id": b2_topic_id,
                "position_x": 100.0,
                "position_y": 100.0,
            },
            headers=auth_headers,
        )
        assert resp.status_code == 404
