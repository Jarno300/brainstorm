"""add users table and user_id to brainstorms

Revision ID: add_users_and_user_id
Revises: make_file_path_nullable
Create Date: 2025-01-15 00:00:00.000000
"""
from typing import Union, Sequence
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


revision: str = "add_users_and_user_id"
down_revision: Union[str, None] = "make_file_path_nullable"
branch_labels: Union[Sequence[str], None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
    # Create users table
    op.create_table(
        "users",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("email", sa.String(255), unique=True, nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("tier", sa.String(50), server_default="free", nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()")),
    )
    op.create_index("ix_users_email", "users", ["email"])
    op.create_index("ix_users_tier", "users", ["tier"])
    op.create_index("ix_users_email_tier", "users", ["email", "tier"])

    # Add user_id to brainstorms (nullable for backward compatibility)
    op.add_column(
        "brainstorms",
        sa.Column("user_id", UUID(as_uuid=True), nullable=True),
    )
    op.create_index("ix_brainstorms_user_id", "brainstorms", ["user_id"])
    op.create_foreign_key(
        "fk_brainstorms_user_id",
        "brainstorms", "users",
        ["user_id"], ["id"],
        ondelete="CASCADE",
    )


def downgrade() -> None:
    op.drop_constraint("fk_brainstorms_user_id", "brainstorms", type_="foreignkey")
    op.drop_index("ix_brainstorms_user_id", table_name="brainstorms")
    op.drop_column("brainstorms", "user_id")

    op.drop_index("ix_users_email_tier", table_name="users")
    op.drop_index("ix_users_tier", table_name="users")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")
