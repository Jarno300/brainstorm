"""add provider_settings table

Revision ID: add_provider_settings
Revises: 0f8a963cea9b
Create Date: 2025-01-01 00:00:00.000000
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID
import uuid


revision: str = 'add_provider_settings'
down_revision: Union[str, None] = '0f8a963cea9b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'provider_settings',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column('provider', sa.String(50), unique=True, nullable=False, index=True),
        sa.Column('api_key', sa.Text, default=''),
        sa.Column('base_url', sa.String(500), default=''),
        sa.Column('created_at', sa.DateTime, nullable=True),
        sa.Column('updated_at', sa.DateTime, nullable=True),
    )


def downgrade() -> None:
    op.drop_table('provider_settings')
