"""add topic_id to messages for topic comments

Revision ID: def456abc789
Revises: abc123def456
Create Date: 2026-06-19 14:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


# revision identifiers, used by Alembic.
revision: str = 'def456abc789'
down_revision: Union[str, None] = 'abc123def456'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'messages',
        sa.Column('topic_id', UUID(as_uuid=True), nullable=True),
    )
    op.create_index('ix_messages_topic_id', 'messages', ['topic_id'])


def downgrade() -> None:
    op.drop_index('ix_messages_topic_id', 'messages')
    op.drop_column('messages', 'topic_id')
