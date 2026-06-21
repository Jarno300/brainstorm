"""add organizations, org_members, org_invites, and org_id on brainstorms

Revision ID: ghi789jkl012
Revises: def456abc789
Create Date: 2026-06-19 16:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


# revision identifiers, used by Alembic.
revision: str = 'ghi789jkl012'
down_revision: Union[str, None] = 'def456abc789'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Organizations table
    op.create_table(
        'organizations',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
    )

    # Organization members
    op.create_table(
        'organization_members',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('organization_id', UUID(as_uuid=True), sa.ForeignKey('organizations.id', ondelete='CASCADE'), nullable=False),
        sa.Column('user_id', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('role', sa.Enum('owner', 'admin', 'editor', 'viewer', name='orgrole', create_type=True), nullable=False, server_default='editor'),
        sa.Column('joined_at', sa.DateTime(), nullable=True),
    )
    op.create_index('ix_org_members_org', 'organization_members', ['organization_id'])
    op.create_index('ix_org_members_user', 'organization_members', ['user_id'])

    # Organization invites
    op.create_table(
        'organization_invites',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('organization_id', UUID(as_uuid=True), sa.ForeignKey('organizations.id', ondelete='CASCADE'), nullable=False),
        sa.Column('email', sa.String(255), nullable=False),
        sa.Column('role', sa.Enum('owner', 'admin', 'editor', 'viewer', name='orgrole', create_type=False), nullable=False, server_default='editor'),
        sa.Column('token', sa.String(64), unique=True, nullable=False),
        sa.Column('created_by', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('accepted_at', sa.DateTime(), nullable=True),
    )
    op.create_index('ix_org_invites_org', 'organization_invites', ['organization_id'])

    # Add organization_id to brainstorms
    op.add_column('brainstorms', sa.Column('organization_id', UUID(as_uuid=True), sa.ForeignKey('organizations.id', ondelete='SET NULL'), nullable=True))
    op.create_index('ix_brainstorms_org', 'brainstorms', ['organization_id'])


def downgrade() -> None:
    op.drop_index('ix_brainstorms_org', 'brainstorms')
    op.drop_column('brainstorms', 'organization_id')
    op.drop_index('ix_org_invites_org', 'organization_invites')
    op.drop_table('organization_invites')
    op.drop_index('ix_org_members_user', 'organization_members')
    op.drop_index('ix_org_members_org', 'organization_members')
    op.drop_table('organization_members')
    op.drop_table('organizations')
    sa.Enum(name='orgrole').drop(op.get_bind(), checkfirst=True)
