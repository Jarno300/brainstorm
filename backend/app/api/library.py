from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
import uuid

from app.database import get_db
from app.schemas.library import LibraryEntryResponse, LibraryFolderResponse, LibraryUpdateRequest
from app.services import library_service, brainstorm_service
from app.api.auth import get_current_user
from app.models.user import User

router = APIRouter(prefix="/api/library", tags=["library"])


@router.get("/{brainstorm_id}", response_model=List[LibraryFolderResponse])
def get_library(brainstorm_id: uuid.UUID, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    brainstorm = brainstorm_service.get_brainstorm(db, brainstorm_id, user_id=current_user.id)
    if not brainstorm:
        raise HTTPException(status_code=404, detail="Brainstorm not found")

    return library_service.get_library_folders(db, brainstorm_id)


@router.get("/entry/{entry_id}", response_model=LibraryEntryResponse)
def get_library_entry(entry_id: uuid.UUID, db: Session = Depends(get_db)):
    entry = library_service.get_library_entry(db, entry_id)
    if not entry:
        raise HTTPException(status_code=404, detail="Library entry not found")
    return entry


@router.put("/entry/{entry_id}", response_model=LibraryEntryResponse)
def update_library_entry(
    entry_id: uuid.UUID,
    data: LibraryUpdateRequest,
    db: Session = Depends(get_db),
):
    entry = library_service.update_library_entry(db, entry_id, data.content)
    if not entry:
        raise HTTPException(status_code=404, detail="Library entry not found")
    return entry
