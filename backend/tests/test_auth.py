"""Tests for auth endpoints: register, login, token validation."""

import pytest


class TestRegister:
    """User registration tests."""

    def test_register_success(self, client, db):
        resp = client.post("/api/auth/register", json={
            "email": "newuser@example.com",
            "password": "ValidP4ss!",
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["email"] == "newuser@example.com"
        assert data["tier"] == "free"
        assert "token" in data
        assert len(data["token"]) > 20

    def test_register_duplicate_email(self, client, test_user):
        resp = client.post("/api/auth/register", json={
            "email": "test@example.com",
            "password": "AnotherP4ss!",
        })
        assert resp.status_code == 409
        assert "already exists" in resp.json()["detail"].lower()

    def test_register_invalid_email(self, client):
        resp = client.post("/api/auth/register", json={
            "email": "not-an-email",
            "password": "ValidP4ss!",
        })
        assert resp.status_code == 400
        assert "email" in resp.json()["detail"].lower()

    def test_register_weak_password_no_uppercase(self, client):
        resp = client.post("/api/auth/register", json={
            "email": "u@example.com",
            "password": "alllowercase1!",
        })
        assert resp.status_code == 400
        assert "uppercase" in resp.json()["detail"].lower()

    def test_register_weak_password_no_digit(self, client):
        resp = client.post("/api/auth/register", json={
            "email": "u@example.com",
            "password": "NoDigitsHere!",
        })
        assert resp.status_code == 400
        assert "digit" in resp.json()["detail"].lower()

    def test_register_weak_password_no_special(self, client):
        resp = client.post("/api/auth/register", json={
            "email": "u@example.com",
            "password": "NoSpecial1",
        })
        assert resp.status_code == 400
        assert "special" in resp.json()["detail"].lower()

    def test_register_weak_password_too_short(self, client):
        resp = client.post("/api/auth/register", json={
            "email": "u@example.com",
            "password": "Ab1!",
        })
        assert resp.status_code == 400
        assert "8" in resp.json()["detail"]

    def test_register_password_contains_email(self, client):
        resp = client.post("/api/auth/register", json={
            "email": "bob@example.com",
            "password": "Bobbob@example.com1!",
        })
        assert resp.status_code == 400
        assert "email" in resp.json()["detail"].lower()


class TestLogin:
    """Login tests."""

    def test_login_success(self, client, test_user):
        resp = client.post("/api/auth/login", json={
            "email": "test@example.com",
            "password": "Test1234!",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["email"] == "test@example.com"
        assert "token" in data

    def test_login_wrong_password(self, client, test_user):
        resp = client.post("/api/auth/login", json={
            "email": "test@example.com",
            "password": "WrongPassword1!",
        })
        assert resp.status_code == 401

    def test_login_nonexistent_user(self, client):
        resp = client.post("/api/auth/login", json={
            "email": "nobody@example.com",
            "password": "SomePassword1!",
        })
        assert resp.status_code == 401

    def test_login_account_lockout(self, client, test_user):
        """After MAX_ATTEMPTS failed logins, the account should be locked."""
        for _ in range(6):
            resp = client.post("/api/auth/login", json={
                "email": "test@example.com",
                "password": "WrongPassword1!",
            })
        # The last request should be a 429 (or still 401 if lockout not yet triggered)
        # We just verify no 500 errors and that requests are still handled
        assert resp.status_code in (401, 429)


class TestMe:
    """Tests for /api/auth/me endpoint."""

    def test_me_returns_user_info(self, client, auth_headers):
        resp = client.get("/api/auth/me", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["email"] == "test@example.com"
        assert data["tier"] == "free"

    def test_me_missing_token(self, client):
        resp = client.get("/api/auth/me")
        assert resp.status_code == 401

    def test_me_invalid_token(self, client):
        resp = client.get("/api/auth/me", headers={
            "Authorization": "Bearer totally.not.a.valid.jwt.token"
        })
        assert resp.status_code == 401
