"""Tests for rate limiting middleware."""

import pytest
from unittest.mock import patch, MagicMock


class TestRateLimitRouteMapping:
    """Tests for the route → limit mapping logic."""

    def test_login_route_limit(self, monkeypatch):
        """Verify login routes have the strictest limit (10/min)."""
        monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
        from app.rate_limit import _get_limits

        window, max_req = _get_limits("/api/auth/login")
        assert max_req == 10
        assert window == 60

    def test_chat_route_limit(self, monkeypatch):
        monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
        from app.rate_limit import _get_limits

        window, max_req = _get_limits("/api/chat/")
        assert max_req == 30
        assert window == 60

    def test_default_limit(self, monkeypatch):
        monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
        from app.rate_limit import _get_limits

        window, max_req = _get_limits("/api/health")
        assert max_req == 120
        assert window == 60


class TestRateLimitMiddlewareStructure:
    """Verify middleware can be constructed and uses a shared pool."""

    def test_middleware_uses_shared_pool(self, monkeypatch):
        monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")

        # Force the pool to be re-created
        import app.rate_limit as rl
        rl._pool = None

        # Create middleware — should init the pool
        middleware = rl.RateLimitMiddleware(app=MagicMock())
        assert rl._pool is not None

        # Create a client from the pool
        client1 = middleware._get_redis()
        client2 = middleware._get_redis()

        # Both clients should come from the same pool
        assert client1.connection_pool is client2.connection_pool


class TestRateLimitHealthEndpoints:
    """Verify health/readiness endpoints are not rate-limited to death."""

    def test_health_working_without_auth(self, client):
        resp = client.get("/api/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "healthy"
        assert "version" in data
        assert "checks" in data
        assert "database" in data["checks"]

    def test_readiness(self, client):
        resp = client.get("/api/health/ready")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ready"
