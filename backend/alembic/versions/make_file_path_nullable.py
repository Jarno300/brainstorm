"""make library_entries.file_path nullable (DB-only storage)

Revision ID: make_file_path_nullable
Revises: add_provider_settings
Create Date: 2025-01-02 00:00:00.000000
"""
from typing import Union, Sequence
from alembic import op
import sqlalchemy as sa


revision: str = "make_file_path_nullable"
down_revision: Union[str, None] = "add_provider_settings"
branch_labels: Union[Sequence[str], None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
    op.alter_column("library_entries", "file_path", nullable=True)


def downgrade() -> None:
    # Set empty-string defaults for existing NULL rows before making NOT NULL
    op.execute("UPDATE library_entries SET file_path = '' WHERE file_path IS NULL")
    op.alter_column("library_entries", "file_path", nullable=False)
