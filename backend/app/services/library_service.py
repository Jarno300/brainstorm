import uuid
from typing import List, Optional
from sqlalchemy.orm import Session
from app.database import utcnow
from app.models.library_entry import LibraryEntry


def create_library_entry(
    db: Session,
    brainstorm_id: uuid.UUID,
    topic_id: Optional[uuid.UUID],
    folder_name: str,
    file_name: str,
    content: str,
    commit: bool = True,
) -> LibraryEntry:
    """Create a library entry. Content stored in DB only — no filesystem I/O."""
    entry = LibraryEntry(
        brainstorm_id=brainstorm_id,
        topic_id=topic_id,
        folder_name=folder_name,
        file_name=file_name,
        file_path="",          # DB-only; file_path kept for backward compatibility
        content=content,
    )
    db.add(entry)
    if commit:
        db.commit()
        db.refresh(entry)
    else:
        db.flush()
    return entry


def get_library_entries(db: Session, brainstorm_id: uuid.UUID) -> List[LibraryEntry]:
    return (
        db.query(LibraryEntry)
        .filter(LibraryEntry.brainstorm_id == brainstorm_id)
        .order_by(LibraryEntry.created_at)
        .all()
    )


def get_library_entry(db: Session, entry_id: uuid.UUID) -> Optional[LibraryEntry]:
    return db.query(LibraryEntry).filter(LibraryEntry.id == entry_id).first()


def get_latest_library_entry_for_topic(db: Session, topic_id: uuid.UUID) -> Optional[LibraryEntry]:
    return (
        db.query(LibraryEntry)
        .filter(LibraryEntry.topic_id == topic_id)
        .order_by(LibraryEntry.created_at.desc())
        .first()
    )


def update_library_entry(db: Session, entry_id: uuid.UUID, content: str) -> Optional[LibraryEntry]:
    """Update library entry content in DB only."""
    entry = get_library_entry(db, entry_id)
    if entry:
        entry.content = content
        entry.updated_at = utcnow()
        db.commit()
        db.refresh(entry)
    return entry


def get_library_folders(db: Session, brainstorm_id: uuid.UUID) -> List[dict]:
    entries = get_library_entries(db, brainstorm_id)
    folders = {}
    for entry in entries:
        if entry.folder_name not in folders:
            folders[entry.folder_name] = []
        folders[entry.folder_name].append(entry)
    return [{"folder_name": k, "entries": v} for k, v in folders.items()]
