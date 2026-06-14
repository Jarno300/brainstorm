"""add share_token and is_published to brainstorms

Revision ID: add_share_token_and_published
Revises: add_users_and_user_id
Create Date: 2025-01-20 00:00:00.000000
"""
from typing import Union, Sequence
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


revision: str = "add_share_token_and_published"
down_revision: Union[str, None] = "add_users_and_user_id"
branch_labels: Union[Sequence[str], None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
    op.add_column(
        "brainstorms",
        sa.Column("share_token", UUID(as_uuid=True), nullable=True, unique=True),
    )
    op.add_column(
        "brainstorms",
        sa.Column("is_published", sa.Boolean(), server_default=sa.text("false"), nullable=False),
    )
    op.create_index("ix_brainstorms_share_token", "brainstorms", ["share_token"])


def downgrade() -> None:
    op.drop_index("ix_brainstorms_share_token", table_name="brainstorms")
    op.drop_column("brainstorms", "is_published")
    op.drop_column("brainstorms", "share_token")
