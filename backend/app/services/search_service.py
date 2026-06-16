"""
Full-text search across brainstorms, messages, and library entries.

Uses PostgreSQL's built-in tsvector/tsquery for fast ranked search.
Falls back to SQLite ILIKE when running locally.
"""

import logging
from typing import List, Optional
from sqlalchemy import text, func, or_
from sqlalchemy.orm import Session

from app.models.brainstorm import Brainstorm
from app.models.message import Message
from app.models.library_entry import LibraryEntry
from app.config import APP_ENV

logger = logging.getLogger(__name__)

MAX_SEARCH_RESULTS = 50
MIN_QUERY_LENGTH = 2

# ── PostgreSQL full-text search configuration ──────────────
_SEARCH_CONFIG = "english"


def _pg_tsvector_search(db: Session, query_str: str, user_id, limit: int = MAX_SEARCH_RESULTS) -> dict:
    """PostgreSQL full-text ranked search across all searchable content."""
    tsquery = " & ".join(
        part + ":*" for part in query_str.split() if len(part) >= MIN_QUERY_LENGTH
    )
    if not tsquery:
        return {"brainstorms": [], "messages": [], "library": []}

    # Search brainstorms
    brainstorm_sql = text("""
        SELECT id, title, summary, ts_rank(
            setweight(to_tsvector(:cfg, coalesce(title, '')), 'A') ||
            setweight(to_tsvector(:cfg, coalesce(summary, '')), 'B'),
            to_tsquery(:cfg, :q)
        ) AS rank
        FROM brainstorms
        WHERE deleted_at IS NULL
          AND user_id = :uid
          AND (
            to_tsvector(:cfg, coalesce(title, '')) ||
            to_tsvector(:cfg, coalesce(summary, ''))
          ) @@ to_tsquery(:cfg, :q)
        ORDER BY rank DESC
        LIMIT :lim
    """)

    # Search messages
    message_sql = text("""
        SELECT m.id, m.brainstorm_id, m.role, m.content, m.created_at,
               b.title AS brainstorm_title,
               ts_rank(
                   setweight(to_tsvector(:cfg, coalesce(m.content, '')), 'A'),
                   to_tsquery(:cfg, :q)
               ) AS rank
        FROM messages m
        JOIN brainstorms b ON b.id = m.brainstorm_id
        WHERE b.deleted_at IS NULL
          AND b.user_id = :uid
          AND to_tsvector(:cfg, coalesce(m.content, '')) @@ to_tsquery(:cfg, :q)
        ORDER BY rank DESC
        LIMIT :lim
    """)

    # Search library entries
    library_sql = text("""
        SELECT le.id, le.brainstorm_id, le.folder_name, le.file_name, le.content,
               b.title AS brainstorm_title,
               ts_rank(
                   setweight(to_tsvector(:cfg, coalesce(le.content, '')), 'A') ||
                   setweight(to_tsvector(:cfg, coalesce(le.folder_name, '')), 'B'),
                   to_tsquery(:cfg, :q)
               ) AS rank
        FROM library_entries le
        JOIN brainstorms b ON b.id = le.brainstorm_id
        WHERE b.deleted_at IS NULL
          AND b.user_id = :uid
          AND (
            to_tsvector(:cfg, coalesce(le.content, '')) ||
            to_tsvector(:cfg, coalesce(le.folder_name, ''))
          ) @@ to_tsquery(:cfg, :q)
        ORDER BY rank DESC
        LIMIT :lim
    """)

    params = {"cfg": _SEARCH_CONFIG, "q": tsquery, "uid": str(user_id), "lim": limit}

    brainstorm_rows = db.execute(brainstorm_sql, params).mappings().all()
    message_rows = db.execute(message_sql, params).mappings().all()
    library_rows = db.execute(library_sql, params).mappings().all()

    return {
        "brainstorms": [
            {"id": str(r["id"]), "title": r["title"], "summary": r.get("summary", ""), "rank": float(r["rank"])}
            for r in brainstorm_rows
        ],
        "messages": [
            {
                "id": str(r["id"]), "brainstorm_id": str(r["brainstorm_id"]),
                "brainstorm_title": r["brainstorm_title"], "role": r["role"],
                "snippet": _snippet(r.get("content", ""), query_str, 200),
                "created_at": str(r["created_at"]) if r.get("created_at") else "",
                "rank": float(r["rank"]),
            }
            for r in message_rows
        ],
        "library": [
            {
                "id": str(r["id"]), "brainstorm_id": str(r["brainstorm_id"]),
                "brainstorm_title": r["brainstorm_title"],
                "folder_name": r["folder_name"], "file_name": r["file_name"],
                "snippet": _snippet(r.get("content", ""), query_str, 200),
                "rank": float(r["rank"]),
            }
            for r in library_rows
        ],
    }


def _sqlite_ilike_search(db: Session, query_str: str, user_id, limit: int = MAX_SEARCH_RESULTS) -> dict:
    """Fallback search using SQLite ILIKE — no ranking, basic substring match."""
    pattern = f"%{query_str}%"

    # Brainstorms
    brainstorms = (
        db.query(Brainstorm)
        .filter(
            Brainstorm.deleted_at.is_(None),
            Brainstorm.user_id == user_id,
            or_(Brainstorm.title.ilike(pattern), Brainstorm.summary.ilike(pattern)),
        )
        .limit(limit)
        .all()
    )

    # Messages
    messages = (
        db.query(Message)
        .join(Brainstorm, Brainstorm.id == Message.brainstorm_id)
        .filter(
            Brainstorm.deleted_at.is_(None),
            Brainstorm.user_id == user_id,
            Message.content.ilike(pattern),
        )
        .order_by(Message.created_at.desc())
        .limit(limit)
        .all()
    )

    # Library entries
    entries = (
        db.query(LibraryEntry)
        .join(Brainstorm, Brainstorm.id == LibraryEntry.brainstorm_id)
        .filter(
            Brainstorm.deleted_at.is_(None),
            Brainstorm.user_id == user_id,
            or_(LibraryEntry.content.ilike(pattern), LibraryEntry.folder_name.ilike(pattern)),
        )
        .limit(limit)
        .all()
    )

    return {
        "brainstorms": [
            {"id": str(b.id), "title": b.title, "summary": b.summary or ""}
            for b in brainstorms
        ],
        "messages": [
            {
                "id": str(m.id), "brainstorm_id": str(m.brainstorm_id),
                "brainstorm_title": m.brainstorm.title if m.brainstorm else "",
                "role": m.role.value if hasattr(m.role, "value") else str(m.role),
                "snippet": _snippet(m.content, query_str, 200),
                "created_at": str(m.created_at),
            }
            for m in messages
        ],
        "library": [
            {
                "id": str(e.id), "brainstorm_id": str(e.brainstorm_id),
                "brainstorm_title": e.brainstorm.title if e.brainstorm else "",
                "folder_name": e.folder_name, "file_name": e.file_name,
                "snippet": _snippet(e.content or "", query_str, 200),
            }
            for e in entries
        ],
    }


def _snippet(content: str, query: str, max_len: int = 200) -> str:
    """Return a relevant snippet around the first match of the query."""
    if not content or not query:
        return content[:max_len] if content else ""

    idx = content.lower().find(query.lower())
    if idx == -1:
        return content[:max_len] + ("…" if len(content) > max_len else "")

    start = max(0, idx - 60)
    end = min(len(content), idx + len(query) + 60)
    snippet = content[start:end]
    if start > 0:
        snippet = "…" + snippet
    if end < len(content):
        snippet = snippet + "…"
    return snippet


def search(db: Session, query_str: str, user_id, limit: int = MAX_SEARCH_RESULTS) -> dict:
    """Full-text search across all user content.

    Uses PostgreSQL tsvector/tsquery in production, SQLite ILIKE in dev.
    """
    if not query_str or len(query_str.strip()) < MIN_QUERY_LENGTH:
        return {"brainstorms": [], "messages": [], "library": []}

    query_str = query_str.strip()
    use_pg = _is_postgresql(db)

    if use_pg:
        try:
            return _pg_tsvector_search(db, query_str, user_id, limit)
        except Exception as e:
            logger.warning("PostgreSQL full-text search error, falling back to ILIKE: %s", e)

    return _sqlite_ilike_search(db, query_str, user_id, limit)


def _is_postgresql(db: Session) -> bool:
    """Check if the database is PostgreSQL."""
    try:
        return "postgresql" in str(db.bind.url).lower()
    except Exception:
        return False
