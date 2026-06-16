"""
Shared test fixtures for the Brainstorm backend.

Uses an in-memory SQLite database for speed and isolation.
Each test gets a fresh database created from the ORM model metadata.
"""

import os
import uuid
from datetime import datetime, timezone
from typing import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

import bcrypt

# ── Override environment before any imports ─────────────────
# Ensure tests never hit a real database or external services.
os.environ.setdefault("APP_ENV", "development")
os.environ.setdefault("APP_LOG_LEVEL", "ERROR")
os.environ.setdefault("OPENAI_API_KEY", "")
os.environ.setdefault("ANTHROPIC_API_KEY", "")
# Use an unreachable Redis URL so the rate limiter fails open during tests.
os.environ.setdefault("REDIS_URL", "redis://127.255.255.255:9999/0")

from app.database import Base, get_db
from app.models.user import User
from app.models.brainstorm import Brainstorm
from app.models.message import Message, MessageRole
from app.models.topic import Topic
from app.models.topic_edge import TopicEdge
from app.models.library_entry import LibraryEntry
from app.models.provider_setting import ProviderSetting
from app.models.map_suggestion_dismissal import MapSuggestionDismissal
from app.main import app


# ── Test database engine (in-memory SQLite) ──────────────────

@pytest.fixture(scope="session")
def engine():
    """Session-scoped engine — created once for all tests."""
    eng = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        echo=False,
    )
    Base.metadata.create_all(bind=eng)
    return eng


@pytest.fixture(scope="function")
def db(engine) -> Generator[Session, None, None]:
    """Per-test database session with automatic rollback."""
    connection = engine.connect()
    transaction = connection.begin()
    session = sessionmaker(bind=connection)()

    yield session

    transaction.rollback()
    session.close()
    connection.close()


@pytest.fixture(scope="function")
def client(db) -> TestClient:
    """FastAPI TestClient wired to the test database."""
    def override_get_db():
        yield db
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


# ── Auth helpers ─────────────────────────────────────────────

def _hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


@pytest.fixture
def test_user(db) -> User:
    """Create a test user and return it."""
    user = User(
        email="test@example.com",
        password_hash=_hash_password("Test1234!"),
        tier="free",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def auth_headers(test_user) -> dict:
    """Return Authorization header dict for the test user using a directly
    generated JWT — avoids hitting the rate-limited login endpoint."""
    import jwt as pyjwt
    from datetime import datetime, timezone, timedelta
    from app.config import SECRET_KEY, JWT_ALGORITHM, JWT_EXPIRATION_HOURS

    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(test_user.id),
        "email": test_user.email,
        "tier": test_user.tier,
        "iat": now,
        "exp": now + timedelta(hours=JWT_EXPIRATION_HOURS),
    }
    token = pyjwt.encode(payload, SECRET_KEY, algorithm=JWT_ALGORITHM)
    return {"Authorization": f"Bearer {token}"}


# ── Data factories ───────────────────────────────────────────

@pytest.fixture
def brainstorm_factory(db, test_user):
    """Factory that creates a Brainstorm for the test user."""
    def _create(title="Test Brainstorm", model="ollama/llama3.2:1b") -> Brainstorm:
        b = Brainstorm(title=title, model=model, user_id=test_user.id)
        db.add(b)
        db.commit()
        db.refresh(b)
        return b
    return _create


@pytest.fixture
def message_factory(db):
    """Factory that creates a Message in a given brainstorm."""
    def _create(brainstorm_id, role="user", content="Hello") -> Message:
        m = Message(
            brainstorm_id=brainstorm_id,
            role=MessageRole[role.upper()],
            content=content,
        )
        db.add(m)
        db.commit()
        db.refresh(m)
        return m
    return _create
