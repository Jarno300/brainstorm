"""add outline to topics

Revision ID: ed1a2b3c4d5e
Revises: c982194ada87
Create Date: 2026-06-16 12:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


# revision identifiers, used by Alembic.
revision: str = 'ed1a2b3c4d5e'
down_revision: Union[str, None] = 'c982194ada87'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'topics',
        sa.Column('outline', JSONB(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('topics', 'outline')
