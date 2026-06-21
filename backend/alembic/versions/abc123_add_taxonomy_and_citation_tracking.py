"""add taxonomy to topics and citation tracking to library entries

Revision ID: abc123def456
Revises: ed1a2b3c4d5e
Create Date: 2026-06-19 12:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


# revision identifiers, used by Alembic.
revision: str = 'abc123def456'
down_revision: Union[str, None] = 'ed1a2b3c4d5e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add taxonomy JSONB column to topics
    op.add_column(
        'topics',
        sa.Column('taxonomy', JSONB(), nullable=True),
    )
    # Add citation tracking columns to library_entries
    op.add_column(
        'library_entries',
        sa.Column('source_type', sa.String(50), nullable=True),
    )
    op.add_column(
        'library_entries',
        sa.Column('source_id', sa.String(255), nullable=True),
    )
    op.add_column(
        'library_entries',
        sa.Column('source_model', sa.String(100), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('topics', 'taxonomy')
    op.drop_column('library_entries', 'source_model')
    op.drop_column('library_entries', 'source_id')
    op.drop_column('library_entries', 'source_type')
