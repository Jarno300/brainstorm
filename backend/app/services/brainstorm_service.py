import uuid
from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import desc, func
from app.database import utcnow
from app.models.brainstorm import Brainstorm
from app.models.message import Message, MessageRole
from app.models.topic import Topic
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
    """List brainstorms with message and topic counts in a single query.

    Uses correlated subqueries via outer joins to avoid the N+1 problem
    that would result from looping and issuing COUNT queries per row.
    """
    # Subquery: message count per brainstorm
    msg_subq = (
        db.query(
            Message.brainstorm_id,
            func.count(Message.id).label("msg_count"),
        )
        .group_by(Message.brainstorm_id)
        .subquery()
    )

    # Subquery: explored (non-proposition) topic count per brainstorm
    topic_subq = (
        db.query(
            Topic.brainstorm_id,
            func.count(Topic.id).label("topic_count"),
        )
        .filter(Topic.is_proposition == False)
        .group_by(Topic.brainstorm_id)
        .subquery()
    )

    query = (
        db.query(
            Brainstorm,
            func.coalesce(msg_subq.c.msg_count, 0).label("msg_count"),
            func.coalesce(topic_subq.c.topic_count, 0).label("topic_count"),
        )
        .outerjoin(msg_subq, Brainstorm.id == msg_subq.c.brainstorm_id)
        .outerjoin(topic_subq, Brainstorm.id == topic_subq.c.brainstorm_id)
        .filter(Brainstorm.deleted_at.is_(None))
    )

    if user_id:
        query = query.filter(Brainstorm.user_id == user_id)

    rows = query.order_by(desc(Brainstorm.updated_at)).offset(skip).limit(limit).all()

    return [
        BrainstormListItem(
            id=b.id,
            title=b.title,
            created_at=b.created_at,
            updated_at=b.updated_at,
            message_count=msg_count,
            explored_topic_count=topic_count,
        )
        for b, msg_count, topic_count in rows
    ]


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
