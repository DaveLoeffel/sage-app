"""Add meeting_notes table for Fireflies integration

Revision ID: 003
Revises: 002
Create Date: 2026-01-16

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '003'
down_revision: Union[str, None] = '002'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'meeting_notes',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('fireflies_id', sa.String(length=255), nullable=False),
        sa.Column('title', sa.String(length=500), nullable=False),
        sa.Column('meeting_date', sa.DateTime(), nullable=True),
        sa.Column('duration_minutes', sa.Integer(), nullable=True),
        sa.Column('participants', postgresql.ARRAY(sa.String()), nullable=True),
        sa.Column('summary', sa.Text(), nullable=True),
        sa.Column('key_points', postgresql.ARRAY(sa.String()), nullable=True),
        sa.Column('action_items', postgresql.ARRAY(sa.String()), nullable=True),
        sa.Column('keywords', postgresql.ARRAY(sa.String()), nullable=True),
        sa.Column('transcript', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('last_synced_at', sa.DateTime(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_meeting_notes_fireflies_id', 'meeting_notes', ['fireflies_id'], unique=True)
    op.create_index('ix_meeting_notes_user_id', 'meeting_notes', ['user_id'], unique=False)
    op.create_index('ix_meeting_notes_user_date', 'meeting_notes', ['user_id', 'meeting_date'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_meeting_notes_user_date', table_name='meeting_notes')
    op.drop_index('ix_meeting_notes_user_id', table_name='meeting_notes')
    op.drop_index('ix_meeting_notes_fireflies_id', table_name='meeting_notes')
    op.drop_table('meeting_notes')
