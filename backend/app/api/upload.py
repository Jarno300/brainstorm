"""File upload API endpoint."""

import uuid
import logging

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session
from pydantic import BaseModel, HttpUrl
from typing import List, Optional

from app.database import get_db
from app.services.upload_service import save_upload, get_uploads
from app.services.url_import_service import import_url
from app.api.auth import get_current_user
from app.models.user import User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/upload", tags=["upload"])


class UploadResponse(BaseModel):
    id: str
    filename: str
    size: int
    text: str


class UploadListItem(BaseModel):
    id: str
    filename: str
    size: int
    uploaded_at: str


@router.post("/{brainstorm_id}", response_model=UploadResponse)
async def upload_file(
    brainstorm_id: uuid.UUID,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Upload a file (PDF, text, or image) and extract its text content."""
    if not file.filename:
        raise HTTPException(status_code=400, detail="Filename is required")

    result = save_upload(db, brainstorm_id, file, current_user.id)
    return UploadResponse(**result)


@router.get("/{brainstorm_id}", response_model=List[UploadListItem])
def list_uploads(
    brainstorm_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List uploaded files for a brainstorm."""
    # Verify ownership
    from app.services.brainstorm_service import get_brainstorm
    brainstorm = get_brainstorm(db, brainstorm_id, user_id=current_user.id)
    if not brainstorm:
        raise HTTPException(status_code=404, detail="Brainstorm not found")

    return get_uploads(brainstorm_id)


# ─── URL Import ───────────────────────────────────────────────

class UrlImportRequest(BaseModel):
    url: HttpUrl
    topic_id: Optional[uuid.UUID] = None


class UrlImportResponse(BaseModel):
    entry_id: str
    title: str
    text_length: int
    site_name: str


@router.post("/{brainstorm_id}/url", response_model=UrlImportResponse)
async def import_from_url(
    brainstorm_id: uuid.UUID,
    data: UrlImportRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Import a web page by URL. Extracts readable text and creates a library entry."""
    from app.services.brainstorm_service import get_brainstorm
    brainstorm = get_brainstorm(db, brainstorm_id, user_id=current_user.id)
    if not brainstorm:
        raise HTTPException(status_code=404, detail="Brainstorm not found")

    try:
        result = await import_url(db, brainstorm_id, str(data.url), data.topic_id)
        return UrlImportResponse(**result)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception("URL import failed")
        raise HTTPException(status_code=500, detail=f"Import failed: {e}")
