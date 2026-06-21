"""add flashcards table

Revision ID: mno345pqr678
Revises: jkl012mno345
Create Date: 2026-06-20 10:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


# revision identifiers, used by Alembic.
revision: str = 'mno345pqr678'
down_revision: Union[str, None] = 'jkl012mno345'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'flashcards',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('brainstorm_id', UUID(as_uuid=True), sa.ForeignKey('brainstorms.id', ondelete='CASCADE'), nullable=False),
        sa.Column('topic_id', UUID(as_uuid=True), sa.ForeignKey('topics.id', ondelete='SET NULL'), nullable=True),
        sa.Column('question', sa.Text(), nullable=False),
        sa.Column('answer', sa.Text(), nullable=False),
        sa.Column('ease_factor', sa.Float(), nullable=False, server_default='2.5'),
        sa.Column('interval', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('repetitions', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('next_review', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('last_reviewed', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index('ix_flashcards_brainstorm_id', 'flashcards', ['brainstorm_id'])
    op.create_index('ix_flashcards_topic_id', 'flashcards', ['topic_id'])
    op.create_index('ix_flashcards_next_review', 'flashcards', ['next_review'])
    op.create_index('ix_flashcards_brainstorm_due', 'flashcards', ['brainstorm_id', 'next_review'])


def downgrade() -> None:
    op.drop_index('ix_flashcards_brainstorm_due', 'flashcards')
    op.drop_index('ix_flashcards_next_review', 'flashcards')
    op.drop_index('ix_flashcards_topic_id', 'flashcards')
    op.drop_index('ix_flashcards_brainstorm_id', 'flashcards')
    op.drop_table('flashcards')
