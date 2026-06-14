import uuid
from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import desc
from app.database import utcnow
from app.models.brainstorm import Brainstorm
from app.models.message import Message, MessageRole
from app.schemas.brainstorm import BrainstormCreate, BrainstormResponse, BrainstormListItem


def _active_query(db: Session):
    """Base query that excludes soft-deleted brainstorms."""
    return db.query(Brainstorm).filter(Brainstorm.deleted_at.is_(None))


def create_brainstorm(db: Session, data: BrainstormCreate, user_id: uuid.UUID | None = None) -> Brainstorm:
    brainstorm = Brainstorm(
        title=data.title,
        model=data.model or "ollama/llama3.2:1b",
        user_id=user_id,
    )
    db.add(brainstorm)
    db.commit()
    db.refresh(brainstorm)
    return brainstorm


def get_brainstorm(db: Session, brainstorm_id: uuid.UUID, user_id: uuid.UUID | None = None) -> Optional[Brainstorm]:
    query = _active_query(db).filter(Brainstorm.id == brainstorm_id)
    if user_id:
        query = query.filter(Brainstorm.user_id == user_id)
    return query.first()


def list_brainstorms(db: Session, skip: int = 0, limit: int = 100, user_id: uuid.UUID | None = None) -> List[BrainstormListItem]:
    query = _active_query(db).order_by(desc(Brainstorm.updated_at))
    if user_id:
        query = query.filter(Brainstorm.user_id == user_id)
    brainstorms = query.offset(skip).limit(limit).all()
    result = []
    for b in brainstorms:
        msg_count = db.query(Message).filter(Message.brainstorm_id == b.id).count()
        result.append(BrainstormListItem(
            id=b.id,
            title=b.title,
            created_at=b.created_at,
            updated_at=b.updated_at,
            message_count=msg_count,
        ))
    return result


def update_brainstorm_title(db: Session, brainstorm_id: uuid.UUID, title: str) -> Optional[Brainstorm]:
    brainstorm = get_brainstorm(db, brainstorm_id)
    if brainstorm:
        brainstorm.title = title
        brainstorm.updated_at = utcnow()
        db.commit()
        db.refresh(brainstorm)
    return brainstorm


def update_brainstorm_model(db: Session, brainstorm_id: uuid.UUID, model: str) -> Optional[Brainstorm]:
    brainstorm = get_brainstorm(db, brainstorm_id)
    if brainstorm:
        brainstorm.model = model
        brainstorm.updated_at = utcnow()
        db.commit()
        db.refresh(brainstorm)
    return brainstorm


def soft_delete_brainstorm(db: Session, brainstorm_id: uuid.UUID) -> bool:
    """Mark a brainstorm as deleted (soft-delete). Sets deleted_at timestamp."""
    brainstorm = get_brainstorm(db, brainstorm_id)
    if brainstorm:
        brainstorm.deleted_at = utcnow()
        db.commit()
        return True
    return False


delete_brainstorm = soft_delete_brainstorm


def generate_share_token(db: Session, brainstorm_id: uuid.UUID, user_id: uuid.UUID) -> str | None:
    """Generate or return an existing share token for a brainstorm."""
    brainstorm = get_brainstorm(db, brainstorm_id, user_id=user_id)
    if not brainstorm:
        return None
    if brainstorm.share_token:
        return str(brainstorm.share_token)
    brainstorm.share_token = uuid.uuid4()
    brainstorm.is_published = True
    db.commit()
    db.refresh(brainstorm)
    return str(brainstorm.share_token)


def revoke_share_token(db: Session, brainstorm_id: uuid.UUID, user_id: uuid.UUID) -> bool:
    """Revoke a share token."""
    brainstorm = get_brainstorm(db, brainstorm_id, user_id=user_id)
    if not brainstorm:
        return False
    brainstorm.share_token = None
    brainstorm.is_published = False
    db.commit()
    return True


def get_brainstorm_by_share_token(db: Session, token: uuid.UUID) -> Optional[Brainstorm]:
    """Look up a published brainstorm by its share token."""
    return _active_query(db).filter(
        Brainstorm.share_token == token,
        Brainstorm.is_published == True,
    ).first()
