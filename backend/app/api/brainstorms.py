from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
import uuid

from app.database import get_db
from app.schemas.brainstorm import BrainstormCreate, BrainstormResponse, BrainstormListItem, BrainstormModelUpdate, BrainstormTitleUpdate
from app.schemas.message import MessageResponse, PaginatedMessagesResponse
from app.services import brainstorm_service, message_service
from app.api.auth import get_current_user
from app.models.user import User

router = APIRouter(prefix="/brainstorms", tags=["brainstorms"])


@router.get("/", response_model=List[BrainstormListItem])
def list_brainstorms(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all brainstorms for the current user."""
    return brainstorm_service.list_brainstorms(db, skip=skip, limit=limit, user_id=current_user.id)


@router.post("/", response_model=BrainstormResponse, status_code=201)
def create_brainstorm(
    data: BrainstormCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new brainstorm session."""
    return brainstorm_service.create_brainstorm(db, data, user_id=current_user.id)


@router.get("/{brainstorm_id}", response_model=BrainstormResponse)
def get_brainstorm(brainstorm_id: uuid.UUID, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    brainstorm = brainstorm_service.get_brainstorm(db, brainstorm_id, user_id=current_user.id)
    if not brainstorm:
        raise HTTPException(status_code=404, detail="Brainstorm not found")
    return brainstorm


@router.delete("/{brainstorm_id}", status_code=204)
def delete_brainstorm(brainstorm_id: uuid.UUID, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    deleted = brainstorm_service.delete_brainstorm(db, brainstorm_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Brainstorm not found")
    return None


@router.patch("/{brainstorm_id}/title", response_model=BrainstormResponse)
def update_title(brainstorm_id: uuid.UUID, data: BrainstormTitleUpdate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    brainstorm = brainstorm_service.update_brainstorm_title(db, brainstorm_id, data.title)
    if not brainstorm:
        raise HTTPException(status_code=404, detail="Brainstorm not found")
    return brainstorm


@router.patch("/{brainstorm_id}/model", response_model=BrainstormResponse)
def update_model(brainstorm_id: uuid.UUID, data: BrainstormModelUpdate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    brainstorm = brainstorm_service.update_brainstorm_model(db, brainstorm_id, data.model)
    if not brainstorm:
        raise HTTPException(status_code=404, detail="Brainstorm not found")
    return brainstorm


@router.get("/{brainstorm_id}/messages", response_model=PaginatedMessagesResponse)
def get_messages(
    brainstorm_id: uuid.UUID,
    limit: int = 50,
    before_id: uuid.UUID | None = None,
    branch_id: uuid.UUID | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get paginated messages for a brainstorm, optionally filtered by branch."""
    messages, has_more = message_service.get_messages(
        db, brainstorm_id, limit=limit, before_id=before_id, branch_id=branch_id,
    )
    cursor = str(messages[0].id) if messages else None
    return PaginatedMessagesResponse(
        messages=messages,
        has_more=has_more,
        before_id=cursor,
    )


@router.post("/{brainstorm_id}/fork/{message_id}")
def fork_branch(
    brainstorm_id: uuid.UUID,
    message_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new conversation branch forking from the given message."""
    brainstorm = brainstorm_service.get_brainstorm(db, brainstorm_id, user_id=current_user.id)
    if not brainstorm:
        raise HTTPException(status_code=404, detail="Brainstorm not found")
    try:
        branch_id = message_service.fork_branch(db, brainstorm_id, message_id)
        return {"branch_id": str(branch_id)}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/{brainstorm_id}/branches")
def get_branches(
    brainstorm_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all conversation branches for a brainstorm."""
    brainstorm = brainstorm_service.get_brainstorm(db, brainstorm_id, user_id=current_user.id)
    if not brainstorm:
        raise HTTPException(status_code=404, detail="Brainstorm not found")
    return message_service.get_branches(db, brainstorm_id)
