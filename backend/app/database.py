import logging
import time
from datetime import datetime, timezone

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, declarative_base
from app.config import DATABASE_URL, APP_ENV

logger = logging.getLogger(__name__)


def utcnow() -> datetime:
    """Timezone-aware UTC now — use instead of deprecated datetime.utcnow()."""
    return datetime.now(timezone.utc)


def wait_for_db(max_retries: int = 10, base_delay: float = 1.0) -> None:
    """Wait for the database to become reachable with exponential backoff.

    Attempts a simple SELECT 1 at increasingly longer intervals.
    Raises RuntimeError if the database is still unreachable after max_retries.

    Called at application startup to avoid crashing if PostgreSQL is still
    initializing (common in Docker Compose environments).
    """
    engine = create_engine(DATABASE_URL, pool_size=1)
    for attempt in range(1, max_retries + 1):
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            logger.info("Database connection established (attempt %d)", attempt)
            engine.dispose()
            return
        except Exception as e:
            engine.dispose()
            if attempt == max_retries:
                raise RuntimeError(
                    f"Could not connect to database after {max_retries} attempts: {e}"
                ) from e
            delay = base_delay * (2 ** (attempt - 1))
            logger.warning(
                "Database connection attempt %d/%d failed, retrying in %.1fs: %s",
                attempt, max_retries, delay, e,
            )
            time.sleep(delay)

# ── Connection pooling ─────────────────────────────────────
_is_sqlite = DATABASE_URL.startswith("sqlite")

_engine_kwargs: dict = {
    "pool_size": 5 if not _is_sqlite else 1,
    "pool_pre_ping": True,
    "pool_recycle": 3600,
}

if _is_sqlite:
    _engine_kwargs["connect_args"] = {"check_same_thread": False}
else:
    _engine_kwargs["max_overflow"] = 10
    if APP_ENV != "development":
        _engine_kwargs["connect_args"] = {"sslmode": "require"}

engine = create_engine(DATABASE_URL, **_engine_kwargs)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    """FastAPI dependency that provides a DB session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


from contextlib import contextmanager

@contextmanager
def task_session():
    """Context manager for Celery task DB sessions.

    Creates a fresh session, commits on success, rolls back on exception,
    and always closes. Use in Celery tasks instead of manual SessionLocal().

    Usage:
        with task_session() as db:
            result = _execute_something(db, ...)
    """
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


async def run_in_db(func):
    """Run a sync DB function in a thread-pool executor with a fresh session.

    Use this inside async streaming endpoints to avoid blocking the event
    loop during DB writes. The function receives a Session and must not
    close it (the wrapper handles cleanup).

    Example:
        await run_in_db(lambda db: create_entry(db, ...))
    """
    import asyncio

    def _runner():
        db = SessionLocal()
        try:
            return func(db)
        finally:
            db.close()

    return await asyncio.get_event_loop().run_in_executor(None, _runner)
