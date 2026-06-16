import io
import logging
import uuid
from zipfile import ZipFile
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.brainstorm import Brainstorm
from app.models.message import Message, MessageRole
from app.models.topic import Topic
from app.models.topic_edge import TopicEdge
from app.models.library_entry import LibraryEntry
from app.models.map_suggestion_dismissal import MapSuggestionDismissal
from app.api.auth import get_current_user
from app.models.user import User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/brainstorms", tags=["export"])


def _serialize(obj):
    """Recursively convert DB model instances and special types to JSON-safe dicts."""
    if obj is None:
        return None
    if isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, uuid.UUID):
        return str(obj)
    if isinstance(obj, MessageRole):
        return obj.value
    if hasattr(obj, "__dict__"):
        data = {}
        for col in obj.__table__.columns:
            val = getattr(obj, col.name)
            data[col.name] = _serialize(val)
        return data
    return obj


@router.get("/{brainstorm_id}/export")
def export_brainstorm(brainstorm_id: uuid.UUID, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Export a complete brainstorm as a downloadable JSON payload."""
    # Include soft-deleted brainstorms in export
    brainstorm = db.query(Brainstorm).filter(Brainstorm.id == brainstorm_id, Brainstorm.user_id == current_user.id).first()
    if not brainstorm:
        raise HTTPException(status_code=404, detail="Brainstorm not found")

    try:
        messages = db.query(Message).filter(
            Message.brainstorm_id == brainstorm_id
        ).order_by(Message.created_at).all()

        topics = db.query(Topic).filter(
            Topic.brainstorm_id == brainstorm_id
        ).order_by(Topic.created_at).all()

        edges = db.query(TopicEdge).filter(
            TopicEdge.brainstorm_id == brainstorm_id
        ).order_by(TopicEdge.created_at).all()

        library = db.query(LibraryEntry).filter(
            LibraryEntry.brainstorm_id == brainstorm_id
        ).order_by(LibraryEntry.created_at).all()

        dismissals = db.query(MapSuggestionDismissal).filter(
            MapSuggestionDismissal.brainstorm_id == brainstorm_id
        ).order_by(MapSuggestionDismissal.created_at).all()

        export_data = {
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "version": "1.0",
            "brainstorm": _serialize(brainstorm),
            "messages": [_serialize(m) for m in messages],
            "topics": [_serialize(t) for t in topics],
            "edges": [_serialize(e) for e in edges],
            "library_entries": [_serialize(l) for l in library],
            "suggestion_dismissals": [_serialize(d) for d in dismissals],
        }

        logger.info(
            "Exported brainstorm %s (%d messages, %d topics, %d edges, %d library entries)",
            brainstorm_id, len(messages), len(topics), len(edges), len(library),
        )

        return export_data

    except Exception as e:
        logger.error("Failed to export brainstorm %s: %s", brainstorm_id, e, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Export failed: {str(e)}")


@router.get("/{brainstorm_id}/export/markdown")
def export_markdown(brainstorm_id: uuid.UUID, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Export library entries as an Obsidian-compatible Markdown .zip."""
    brainstorm = db.query(Brainstorm).filter(Brainstorm.id == brainstorm_id, Brainstorm.user_id == current_user.id).first()
    if not brainstorm:
        raise HTTPException(status_code=404, detail="Brainstorm not found")

    entries = db.query(LibraryEntry).filter(
        LibraryEntry.brainstorm_id == brainstorm_id
    ).order_by(LibraryEntry.folder_name, LibraryEntry.file_name).all()

    if not entries:
        raise HTTPException(status_code=404, detail="No library entries to export")

    buf = io.BytesIO()
    with ZipFile(buf, "w") as zf:
        # Collect folders and their entries
        folders: dict[str, list] = {}
        for entry in entries:
            folder = entry.folder_name or "uncategorized"
            folders.setdefault(folder, []).append(entry)

        # Write each entry as a markdown file inside its folder
        for folder_name, folder_entries in sorted(folders.items()):
            for entry in folder_entries:
                # Clean filename: remove timestamp prefix for readability
                file_name = entry.file_name
                if not file_name.endswith(".md"):
                    file_name += ".md"
                path = f"{folder_name}/{file_name}"
                zf.writestr(path, entry.content or f"# {entry.folder_name}\n\n*No content.*")

        # Write _index.md at root with wikilinks to all topics
        index_lines = [f"# {brainstorm.title}\n", f"\n*Exported {datetime.now(timezone.utc).strftime('%Y-%m-%d')}*\n"]
        for folder_name in sorted(folders.keys()):
            index_lines.append(f"\n## {folder_name}\n")
            for entry in folders[folder_name]:
                file_name = entry.file_name
                if not file_name.endswith(".md"):
                    file_name += ".md"
                # Obsidian-compatible wikilink
                display_name = file_name.replace(".md", "").replace("_", " ").replace("-", " ").title()
                index_lines.append(f"- [[{folder_name}/{file_name}|{display_name}]]\n")

        zf.writestr("_index.md", "".join(index_lines))

        # Write a minimal Obsidian vault config
        zf.writestr(".obsidian/app.json", '{"showLineNumber":true,"alwaysUpdateLinks":true}')
        zf.writestr(".obsidian/core-plugins.json", '["file-explorer","graph","search","outgoing-link","tag-explorer"]')

    buf.seek(0)
    filename = f"{brainstorm.title.replace(' ', '_')}_markdown.zip"
    return StreamingResponse(
        buf,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
