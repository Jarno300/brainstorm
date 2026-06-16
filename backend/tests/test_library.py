"""Tests for library endpoints including ownership verification."""

import uuid
import pytest

from app.models.library_entry import LibraryEntry
from app.models.brainstorm import Brainstorm
from app.models.user import User
import bcrypt


class TestLibraryOwnership:
    """Verify library entry endpoints enforce user ownership."""

    @pytest.fixture
    def other_user(self, db) -> User:
        user = User(
            email="other@example.com",
            password_hash=bcrypt.hashpw("OtherP4ss!".encode(), bcrypt.gensalt()).decode(),
            tier="free",
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return user

    @pytest.fixture
    def other_brainstorm(self, db, other_user) -> Brainstorm:
        b = Brainstorm(title="Other's Brainstorm", model="ollama/llama3.2:1b", user_id=other_user.id)
        db.add(b)
        db.commit()
        db.refresh(b)
        return b

    @pytest.fixture
    def other_library_entry(self, db, other_brainstorm) -> LibraryEntry:
        e = LibraryEntry(
            brainstorm_id=other_brainstorm.id,
            folder_name="test-folder",
            file_name="test.md",
            content="# Hello",
        )
        db.add(e)
        db.commit()
        db.refresh(e)
        return e

    def test_cannot_get_foreign_library_entry(self, client, auth_headers, other_library_entry):
        """User A should not be able to read User B's library entry."""
        resp = client.get(
            f"/api/library/entry/{other_library_entry.id}",
            headers=auth_headers,
        )
        assert resp.status_code == 404

    def test_cannot_update_foreign_library_entry(self, client, auth_headers, other_library_entry):
        """User A should not be able to modify User B's library entry."""
        resp = client.put(
            f"/api/library/entry/{other_library_entry.id}",
            json={"content": "Hacked!"},
            headers=auth_headers,
        )
        assert resp.status_code == 404

    def test_cannot_delete_foreign_library_entry(self, client, auth_headers, other_library_entry):
        """User A should not be able to delete User B's library entry."""
        resp = client.delete(
            f"/api/library/entry/{other_library_entry.id}",
            headers=auth_headers,
        )
        assert resp.status_code == 404


class TestLibraryCRUD:
    """Tests for library CRUD operations on own entries."""

    def test_get_own_library_entry(self, client, auth_headers, brainstorm_factory, db):
        b = brainstorm_factory(title="My Brainstorm")
        e = LibraryEntry(
            brainstorm_id=b.id,
            folder_name="my-folder",
            file_name="notes.md",
            content="# My Notes",
        )
        db.add(e)
        db.commit()
        db.refresh(e)

        resp = client.get(f"/api/library/entry/{e.id}", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["folder_name"] == "my-folder"
        assert data["content"] == "# My Notes"

    def test_update_own_library_entry(self, client, auth_headers, brainstorm_factory, db):
        b = brainstorm_factory(title="My Brainstorm")
        e = LibraryEntry(
            brainstorm_id=b.id,
            folder_name="my-folder",
            file_name="notes.md",
            content="Original content",
        )
        db.add(e)
        db.commit()
        db.refresh(e)

        resp = client.put(
            f"/api/library/entry/{e.id}",
            json={"content": "Updated content"},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["content"] == "Updated content"

    def test_delete_own_library_entry(self, client, auth_headers, brainstorm_factory, db):
        b = brainstorm_factory(title="My Brainstorm")
        e = LibraryEntry(
            brainstorm_id=b.id,
            folder_name="my-folder",
            file_name="notes.md",
            content="To be deleted",
        )
        db.add(e)
        db.commit()
        db.refresh(e)

        resp = client.delete(f"/api/library/entry/{e.id}", headers=auth_headers)
        assert resp.status_code == 204

        # Verify it's gone
        get_resp = client.get(f"/api/library/entry/{e.id}", headers=auth_headers)
        assert get_resp.status_code == 404
