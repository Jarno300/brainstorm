import uuid
from typing import List, Optional
from sqlalchemy.orm import Session
from app.models.message import Message, MessageRole


def create_message(db: Session, brainstorm_id: uuid.UUID, role: str, content: str, commit: bool = True) -> Message:
    message = Message(
        brainstorm_id=brainstorm_id,
        role=MessageRole(role),
        content=content,
    )
    db.add(message)
    if commit:
        db.commit()
        db.refresh(message)
    else:
        db.flush()
    return message


def get_messages(db: Session, brainstorm_id: uuid.UUID) -> List[Message]:
    return (
        db.query(Message)
        .filter(Message.brainstorm_id == brainstorm_id)
        .order_by(Message.created_at)
        .all()
    )


def get_message(db: Session, message_id: uuid.UUID) -> Optional[Message]:
    return db.query(Message).filter(Message.id == message_id).first()
