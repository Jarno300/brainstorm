"""API Key management — create, list, revoke programmatic access tokens."""

import uuid
import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime

from app.database import get_db
from app.api.auth import get_current_user
from app.models.user import User
from app.models.api_key import ApiKey

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api-keys", tags=["api-keys"])


class ApiKeyCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    scopes: str = "read write"


class ApiKeyResponse(BaseModel):
    id: str
    name: str
    key_prefix: str
    scopes: str
    is_active: bool
    last_used_at: Optional[datetime]
    created_at: datetime


class ApiKeyCreatedResponse(BaseModel):
    id: str
    name: str
    key: str  # Full key — only shown once!
    key_prefix: str
    scopes: str
    created_at: datetime


@router.post("/", response_model=ApiKeyCreatedResponse, status_code=201)
def create_api_key(
    data: ApiKeyCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new API key. The full key is returned only once — save it immediately."""
    raw_key, key_prefix, key_hash = ApiKey.generate()

    key = ApiKey(
        user_id=current_user.id,
        name=data.name,
        key_prefix=key_prefix,
        key_hash=key_hash,
        scopes=data.scopes,
    )
    db.add(key)
    db.commit()
    db.refresh(key)

    logger.info("api_key_created | user=%s key=%s", current_user.id, key.id)
    return ApiKeyCreatedResponse(
        id=str(key.id),
        name=key.name,
        key=raw_key,
        key_prefix=key.key_prefix,
        scopes=key.scopes,
        created_at=key.created_at,
    )


@router.get("/", response_model=List[ApiKeyResponse])
def list_api_keys(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all API keys for the current user. Key values are never returned."""
    keys = (
        db.query(ApiKey)
        .filter(ApiKey.user_id == current_user.id)
        .order_by(ApiKey.created_at.desc())
        .all()
    )
    return [
        ApiKeyResponse(
            id=str(k.id),
            name=k.name,
            key_prefix=k.key_prefix,
            scopes=k.scopes,
            is_active=k.is_active,
            last_used_at=k.last_used_at,
            created_at=k.created_at,
        )
        for k in keys
    ]


@router.delete("/{key_id}", status_code=204)
def revoke_api_key(
    key_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Revoke (delete) an API key."""
    key = (
        db.query(ApiKey)
        .filter(ApiKey.id == key_id, ApiKey.user_id == current_user.id)
        .first()
    )
    if not key:
        raise HTTPException(status_code=404, detail="API key not found")

    db.delete(key)
    db.commit()
    logger.info("api_key_revoked | user=%s key=%s", current_user.id, key_id)
    return None
