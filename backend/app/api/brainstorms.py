from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
import uuid

from app.database import get_db
from app.schemas.brainstorm import BrainstormCreate, BrainstormResponse, BrainstormListItem, BrainstormModelUpdate
from app.schemas.message import MessageResponse
from app.services import brainstorm_service, message_service
from app.api.auth import get_current_user
from app.models.user import User

router = APIRouter(prefix="/api/brainstorms", tags=["brainstorms"])


@router.get("/", response_model=List[BrainstormListItem])
def list_brainstorms(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return brainstorm_service.list_brainstorms(db, skip=skip, limit=limit, user_id=current_user.id)


@router.post("/", response_model=BrainstormResponse, status_code=201)
def create_brainstorm(data: BrainstormCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
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
def update_title(brainstorm_id: uuid.UUID, title: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    brainstorm = brainstorm_service.update_brainstorm_title(db, brainstorm_id, title)
    if not brainstorm:
        raise HTTPException(status_code=404, detail="Brainstorm not found")
    return brainstorm


@router.patch("/{brainstorm_id}/model", response_model=BrainstormResponse)
def update_model(brainstorm_id: uuid.UUID, data: BrainstormModelUpdate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    brainstorm = brainstorm_service.update_brainstorm_model(db, brainstorm_id, data.model)
    if not brainstorm:
        raise HTTPException(status_code=404, detail="Brainstorm not found")
    return brainstorm


@router.get("/{brainstorm_id}/messages", response_model=List[MessageResponse])
def get_messages(brainstorm_id: uuid.UUID, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return message_service.get_messages(db, brainstorm_id)
