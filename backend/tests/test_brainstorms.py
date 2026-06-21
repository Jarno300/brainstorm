"""Tests for brainstorms CRUD endpoints."""

import uuid
import pytest


class TestListBrainstorms:
    """Tests for GET /api/brainstorms/"""

    def test_list_empty(self, client, auth_headers):
        resp = client.get("/api/brainstorms/", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_brainstorms(self, client, auth_headers, brainstorm_factory):
        b1 = brainstorm_factory(title="Alpha")
        b2 = brainstorm_factory(title="Beta")

        resp = client.get("/api/brainstorms/", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2
        titles = {item["title"] for item in data}
        assert titles == {"Alpha", "Beta"}

    def test_list_requires_auth(self, client):
        resp = client.get("/api/brainstorms/")
        assert resp.status_code == 401


class TestCreateBrainstorm:
    """Tests for POST /api/brainstorms/"""

    def test_create_brainstorm(self, client, auth_headers):
        resp = client.post("/api/brainstorms/", json={
            "title": "My Research",
        }, headers=auth_headers)
        assert resp.status_code == 201
        data = resp.json()
        assert data["title"] == "My Research"
        from app.config import DEFAULT_MODEL
        assert data["model"] == DEFAULT_MODEL
        assert "id" in data

    def test_create_brainstorm_with_model(self, client, auth_headers):
        resp = client.post("/api/brainstorms/", json={
            "title": "GPT Research",
            "model": "openai/gpt-4o-mini",
        }, headers=auth_headers)
        assert resp.status_code == 201
        data = resp.json()
        assert data["model"] == "openai/gpt-4o-mini"

    def test_create_brainstorm_requires_auth(self, client):
        resp = client.post("/api/brainstorms/", json={
            "title": "Should fail",
        })
        assert resp.status_code == 401


class TestGetBrainstorm:
    """Tests for GET /api/brainstorms/{id}"""

    def test_get_brainstorm(self, client, auth_headers, brainstorm_factory):
        b = brainstorm_factory(title="My Brainstorm")

        resp = client.get(f"/api/brainstorms/{b.id}", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["title"] == "My Brainstorm"
        assert data["id"] == str(b.id)

    def test_get_nonexistent(self, client, auth_headers):
        fake_id = uuid.uuid4()
        resp = client.get(f"/api/brainstorms/{fake_id}", headers=auth_headers)
        assert resp.status_code == 404

    def test_get_requires_auth(self, client, brainstorm_factory):
        b = brainstorm_factory(title="Should be hidden")
        resp = client.get(f"/api/brainstorms/{b.id}")
        assert resp.status_code == 401


class TestDeleteBrainstorm:
    """Tests for DELETE /api/brainstorms/{id} (soft-delete)"""

    def test_soft_delete(self, client, auth_headers, brainstorm_factory):
        b = brainstorm_factory(title="Delete Me")

        resp = client.delete(f"/api/brainstorms/{b.id}", headers=auth_headers)
        assert resp.status_code == 204

        # Should no longer appear in list
        list_resp = client.get("/api/brainstorms/", headers=auth_headers)
        assert list_resp.status_code == 200
        ids = {item["id"] for item in list_resp.json()}
        assert str(b.id) not in ids

        # Direct get should also 404
        get_resp = client.get(f"/api/brainstorms/{b.id}", headers=auth_headers)
        assert get_resp.status_code == 404


class TestUpdateTitle:
    """Tests for PATCH /api/brainstorms/{id}/title"""

    def test_update_title(self, client, auth_headers, brainstorm_factory):
        b = brainstorm_factory(title="Old Title")

        resp = client.patch(
            f"/api/brainstorms/{b.id}/title",
            json={"title": "New Title"},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["title"] == "New Title"


class TestGetMessages:
    """Tests for GET /api/brainstorms/{id}/messages"""

    def test_get_messages(self, client, auth_headers, brainstorm_factory, message_factory):
        b = brainstorm_factory(title="Chat")
        message_factory(b.id, role="user", content="Hello")
        message_factory(b.id, role="assistant", content="Hi there!")

        resp = client.get(f"/api/brainstorms/{b.id}/messages", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "messages" in data
        assert len(data["messages"]) == 2
        assert data["has_more"] == False
        assert data["before_id"] is not None
        roles = {m["role"] for m in data["messages"]}
        assert roles == {"user", "assistant"}

    def test_get_messages_pagination(self, client, auth_headers, brainstorm_factory, message_factory):
        """Test cursor-based pagination."""
        import time as _time
        b = brainstorm_factory(title="Paginated")
        # Small delays ensure distinct timestamps
        for i in range(5):
            message_factory(b.id, role="user", content=f"Message {i}")
            _time.sleep(0.01)

        # First page: 2 messages
        resp = client.get(f"/api/v1/brainstorms/{b.id}/messages?limit=2", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["messages"]) == 2
        assert data["has_more"] == True
        cursor = data["before_id"]

        # Second page using cursor
        resp2 = client.get(
            f"/api/v1/brainstorms/{b.id}/messages?limit=2&before_id={cursor}",
            headers=auth_headers,
        )
        assert resp2.status_code == 200
        data2 = resp2.json()
        assert len(data2["messages"]) == 2
        assert data2["has_more"] == True

        # Third page (only 1 remaining)
        cursor2 = data2["before_id"]
        resp3 = client.get(
            f"/api/v1/brainstorms/{b.id}/messages?limit=2&before_id={cursor2}",
            headers=auth_headers,
        )
        assert resp3.status_code == 200
        data3 = resp3.json()
        assert len(data3["messages"]) == 1
        assert data3["has_more"] == False
