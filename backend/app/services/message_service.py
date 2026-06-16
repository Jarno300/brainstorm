import uuid
from typing import List, Optional, Tuple
from sqlalchemy import func
from sqlalchemy.orm import Session
from app.models.message import Message, MessageRole

# ── Pagination defaults ──────────────────────────────────────
DEFAULT_MESSAGE_LIMIT = 50
MAX_MESSAGE_LIMIT = 200


def create_message(
    db: Session,
    brainstorm_id: uuid.UUID,
    role: str,
    content: str,
    branch_id: Optional[uuid.UUID] = None,
    parent_message_id: Optional[uuid.UUID] = None,
    commit: bool = True,
) -> Message:
    message = Message(
        brainstorm_id=brainstorm_id,
        role=MessageRole(role),
        content=content,
        branch_id=branch_id,
        parent_message_id=parent_message_id,
    )
    db.add(message)
    if commit:
        db.commit()
        db.refresh(message)
    else:
        db.flush()
    return message


def fork_branch(
    db: Session,
    brainstorm_id: uuid.UUID,
    parent_message_id: uuid.UUID,
) -> uuid.UUID:
    """Create a new branch forking from the specified message.

    Returns the new branch_id. Messages after the fork point will
    use this branch_id.
    """
    # Verify parent message exists
    parent = (
        db.query(Message)
        .filter(Message.id == parent_message_id, Message.brainstorm_id == brainstorm_id)
        .first()
    )
    if not parent:
        raise ValueError("Parent message not found")

    new_branch_id = uuid.uuid4()
    return new_branch_id


def get_branches(db: Session, brainstorm_id: uuid.UUID) -> list:
    """List all branches in a brainstorm with their message counts."""
    rows = (
        db.query(
            Message.branch_id,
            func.count(Message.id).label("count"),
            func.min(Message.created_at).label("first_at"),
            func.max(Message.created_at).label("last_at"),
        )
        .filter(Message.brainstorm_id == brainstorm_id)
        .group_by(Message.branch_id)
        .all()
    )

    branches = []
    for row in rows:
        bid = row.branch_id or brainstorm_id  # root branch uses brainstorm_id as key
        # Get first user message as branch label
        first_msg = (
            db.query(Message)
            .filter(
                Message.brainstorm_id == brainstorm_id,
                Message.branch_id == row.branch_id,
                Message.role == MessageRole("user"),
            )
            .order_by(Message.created_at)
            .first()
        )
        label = first_msg.content[:60] + "…" if first_msg and len(first_msg.content) > 60 else (first_msg.content if first_msg else "Empty branch")

        branches.append({
            "id": str(bid),
            "label": label,
            "message_count": row.count,
            "first_at": str(row.first_at) if row.first_at else "",
            "last_at": str(row.last_at) if row.last_at else "",
        })

    return sorted(branches, key=lambda b: b["first_at"])


def get_messages(
    db: Session,
    brainstorm_id: uuid.UUID,
    limit: int = DEFAULT_MESSAGE_LIMIT,
    before_id: Optional[uuid.UUID] = None,
    branch_id: Optional[uuid.UUID] = None,
) -> Tuple[List[Message], bool]:
    """Return paginated messages for a brainstorm, newest first.

    If branch_id is provided, only messages from that branch are returned.
    If branch_id is None (not provided), returns the root/main branch
    where branch_id IS NULL.
    """
    limit = min(max(1, limit), MAX_MESSAGE_LIMIT)

    query = (
        db.query(Message)
        .filter(Message.brainstorm_id == brainstorm_id)
    )

    # Branch filter: explicit branch_id, or root branch (NULL)
    if branch_id is not None:
        query = query.filter(Message.branch_id == branch_id)
    else:
        query = query.filter(Message.branch_id.is_(None))

    if before_id is not None:
        # Find the cursor message's timestamp
        cursor_msg = db.query(Message).filter(Message.id == before_id).first()
        if cursor_msg:
            query = query.filter(Message.created_at < cursor_msg.created_at)

    # Fetch one extra to determine has_more
    messages = (
        query
        .order_by(Message.created_at.desc())
        .limit(limit + 1)
        .all()
    )

    has_more = len(messages) > limit
    result = messages[:limit]

    # Return in chronological order for the frontend
    result.reverse()

    return result, has_more


def get_message(db: Session, message_id: uuid.UUID) -> Optional[Message]:
    return db.query(Message).filter(Message.id == message_id).first()
