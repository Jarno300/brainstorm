from datetime import datetime, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from app.config import DATABASE_URL, APP_ENV


def utcnow() -> datetime:
    """Timezone-aware UTC now — use instead of deprecated datetime.utcnow()."""
    return datetime.now(timezone.utc)

# ── Connection pooling ─────────────────────────────────────
# Production PostgreSQL: tune pool_size to match expected concurrency
# Local dev SQLite: pool_size=1 (SQLite doesn't support concurrent writes)
_is_sqlite = DATABASE_URL.startswith("sqlite")

engine = create_engine(
    DATABASE_URL,
    pool_size=5 if not _is_sqlite else 1,
    max_overflow=10 if not _is_sqlite else 0,
    pool_pre_ping=True,          # verify connections before use
    pool_recycle=3600,           # recycle connections after 1 hour
    connect_args=(
        {"check_same_thread": False} if _is_sqlite
        else {"sslmode": "require"} if APP_ENV != "development"
        else {}
    ),
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    """FastAPI dependency that provides a DB session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
