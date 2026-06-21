import io
import logging
import uuid
from xml.etree import ElementTree as ET
from zipfile import ZipFile
from datetime import datetime, timezone
from pydantic import BaseModel
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


@router.get("/{brainstorm_id}/export/opml")
def export_opml(brainstorm_id: uuid.UUID, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Export the knowledge map as OPML (mind-map interchange format).

    Compatible with MindNode, XMind, Freeplane, OmniOutliner, and other mind-mapping tools.
    Builds a hierarchy from topic taxonomy: parent topics → child topics → related topics.
    """
    brainstorm = db.query(Brainstorm).filter(Brainstorm.id == brainstorm_id, Brainstorm.user_id == current_user.id).first()
    if not brainstorm:
        raise HTTPException(status_code=404, detail="Brainstorm not found")

    topics = db.query(Topic).filter(
        Topic.brainstorm_id == brainstorm_id, Topic.is_proposition == False
    ).order_by(Topic.confidence.desc()).all()

    if not topics:
        raise HTTPException(status_code=404, detail="No topics to export")

    edges = db.query(TopicEdge).filter(
        TopicEdge.brainstorm_id == brainstorm_id,
        ~TopicEdge.relationship.startswith("suggestion:"),
    ).all()

    # Build adjacency: topic_id → list of connected topic_ids
    topic_ids = {t.id for t in topics}
    adj: dict[uuid.UUID, list] = {t.id: [] for t in topics}
    for e in edges:
        if e.source_topic_id in topic_ids and e.target_topic_id in topic_ids:
            adj[e.source_topic_id].append(e.target_topic_id)
            adj[e.target_topic_id].append(e.source_topic_id)

    # Identify root topics (highest confidence, or those with no parent taxonomy)
    topic_map = {t.id: t for t in topics}

    # Sort by confidence for root selection
    sorted_topics = sorted(topics, key=lambda t: t.confidence or 0, reverse=True)

    # Build OPML
    opml = ET.Element("opml", version="2.0")
    head = ET.SubElement(opml, "head")
    ET.SubElement(head, "title").text = brainstorm.title
    ET.SubElement(head, "dateCreated").text = brainstorm.created_at.isoformat() if brainstorm.created_at else ""
    body = ET.SubElement(opml, "body")

    # Recursively build outline elements
    visited = set()

    def _build_outline(parent_el, topic, depth=0):
        if topic.id in visited or depth > 4:
            return
        visited.add(topic.id)
        display = topic.name.replace("-", " ").title()
        note = topic.description or ""
        attrs = {"text": display}
        if note:
            attrs["_note"] = note
        outline = ET.SubElement(parent_el, "outline", **attrs)
        # Add connected topics as children
        for neighbor_id in adj.get(topic.id, [])[:5]:
            neighbor = topic_map.get(neighbor_id)
            if neighbor and neighbor.id not in visited:
                _build_outline(outline, neighbor, depth + 1)

    # Root from highest-confidence topics
    for topic in sorted_topics:
        if topic.id not in visited:
            _build_outline(body, topic)

    # Serialize
    ET.indent(opml, space="  ")
    xml_str = '<?xml version="1.0" encoding="UTF-8"?>\n' + ET.tostring(opml, encoding="unicode")

    filename = f"{brainstorm.title.replace(' ', '_')}.opml"
    return StreamingResponse(
        io.BytesIO(xml_str.encode("utf-8")),
        media_type="application/xml",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ─── Import (re-create from export JSON) ─────────────────────

class ImportBrainstormRequest(BaseModel):
    title: str | None = None  # Override title; uses original if not set
    data: dict  # The full export JSON payload


class ImportBrainstormResponse(BaseModel):
    id: str
    title: str
    topics_imported: int
    edges_imported: int
    library_entries_imported: int


@router.post("/{brainstorm_id}/export/import")
def import_brainstorm(
    brainstorm_id: uuid.UUID,
    request: ImportBrainstormRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Import a brainstorm from an exported JSON payload.

    Re-creates topics, edges, and library entries. Maps old IDs to new ones.
    """
    # Validate target brainstorm exists
    brainstorm = db.query(Brainstorm).filter(
        Brainstorm.id == brainstorm_id, Brainstorm.user_id == current_user.id
    ).first()
    if not brainstorm:
        raise HTTPException(status_code=404, detail="Brainstorm not found")

    data = request.data
    if not isinstance(data, dict):
        raise HTTPException(status_code=400, detail="Invalid export data: expected a JSON object")

    topics_data = data.get("topics", []) or []
    edges_data = data.get("edges", []) or []
    library_data = data.get("library_entries", []) or []

    if not topics_data:
        raise HTTPException(status_code=400, detail="Export contains no topics")

    # Map old IDs → new IDs
    id_map: dict[str, uuid.UUID] = {}

    topics_imported = 0
    for t_data in topics_data:
        if not isinstance(t_data, dict):
            continue
        name = str(t_data.get("name", "")).strip()
        if not name:
            continue
        new_id = uuid.uuid4()
        id_map[str(t_data.get("id", ""))] = new_id
        topic = Topic(
            id=new_id,
            brainstorm_id=brainstorm_id,
            name=name[:255],
            description=str(t_data.get("description", ""))[:10000],
            confidence=float(t_data.get("confidence", 0.5)),
            is_proposition=bool(t_data.get("is_proposition", False)),
            position_x=float(t_data.get("position_x", 0)),
            position_y=float(t_data.get("position_y", 0)),
        )
        db.add(topic)
        topics_imported += 1

    edges_imported = 0
    for e_data in edges_data:
        if not isinstance(e_data, dict):
            continue
        old_source = str(e_data.get("source_topic_id", ""))
        old_target = str(e_data.get("target_topic_id", ""))
        new_source = id_map.get(old_source)
        new_target = id_map.get(old_target)
        if not new_source or not new_target:
            continue
        # Skip if edge already exists
        existing = db.query(TopicEdge).filter(
            TopicEdge.brainstorm_id == brainstorm_id,
            TopicEdge.source_topic_id == new_source,
            TopicEdge.target_topic_id == new_target,
        ).first()
        if existing:
            continue
        edge = TopicEdge(
            id=uuid.uuid4(),
            brainstorm_id=brainstorm_id,
            source_topic_id=new_source,
            target_topic_id=new_target,
            relationship=str(e_data.get("relationship", "related"))[:50],
            weight=float(e_data.get("weight", 0.5)),
        )
        db.add(edge)
        edges_imported += 1

    library_imported = 0
    for l_data in library_data:
        if not isinstance(l_data, dict):
            continue
        old_topic_id = str(l_data.get("topic_id", ""))
        new_topic_id = id_map.get(old_topic_id)
        entry = LibraryEntry(
            id=uuid.uuid4(),
            brainstorm_id=brainstorm_id,
            topic_id=new_topic_id,
            folder_name=str(l_data.get("folder_name", "Imported"))[:255],
            file_name=str(l_data.get("file_name", "imported.md"))[:255],
            content=str(l_data.get("content", "")),
            source_type="import",
        )
        db.add(entry)
        library_imported += 1

    db.commit()

    logger.info(
        "import_brainstorm done | brainstorm=%s topics=%d edges=%d library=%d",
        brainstorm_id, topics_imported, edges_imported, library_imported,
    )

    return ImportBrainstormResponse(
        id=str(brainstorm_id),
        title=brainstorm.title,
        topics_imported=topics_imported,
        edges_imported=edges_imported,
        library_entries_imported=library_imported,
    )
