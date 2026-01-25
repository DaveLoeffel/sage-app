"""Add todo_items table.

Revision ID: 005
Revises: 004
Create Date: 2026-01-20

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '005'
down_revision: Union[str, None] = '004'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create todo_items table
    op.create_table(
        'todo_items',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),

        # Core todo info
        sa.Column('title', sa.String(500), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),

        # Classification
        sa.Column('category', sa.Enum('self_reminder', 'request_received', 'commitment_made', 'meeting_action', 'manual', name='todocategory'), nullable=False),
        sa.Column('priority', sa.Enum('low', 'normal', 'high', 'urgent', name='todopriority'), nullable=False, server_default='normal'),
        sa.Column('status', sa.Enum('pending', 'snoozed', 'completed', 'cancelled', name='todostatus'), nullable=False, server_default='pending'),

        # Timing
        sa.Column('due_date', sa.Date(), nullable=True),
        sa.Column('snoozed_until', sa.Date(), nullable=True),

        # Source tracking
        sa.Column('source_type', sa.String(50), nullable=False),
        sa.Column('source_id', sa.String(255), nullable=True),
        sa.Column('source_summary', sa.String(500), nullable=True),

        # Contact info
        sa.Column('contact_name', sa.String(255), nullable=True),
        sa.Column('contact_email', sa.String(255), nullable=True),

        # AI detection metadata
        sa.Column('detection_confidence', sa.Float(), nullable=True),
        sa.Column('detected_deadline_text', sa.String(255), nullable=True),

        # Action timestamps
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('completed_reason', sa.String(255), nullable=True),

        # Timestamps
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('NOW()')),

        # Constraints
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    )

    # Create indexes
    op.create_index('ix_todo_items_user_id', 'todo_items', ['user_id'])
    op.create_index('ix_todo_items_category', 'todo_items', ['category'])
    op.create_index('ix_todo_items_priority', 'todo_items', ['priority'])
    op.create_index('ix_todo_items_status', 'todo_items', ['status'])
    op.create_index('ix_todo_items_due_date', 'todo_items', ['due_date'])
    op.create_index('ix_todo_items_source_id', 'todo_items', ['source_id'])
    op.create_index('ix_todo_items_contact_email', 'todo_items', ['contact_email'])
    op.create_index('ix_todo_status_due', 'todo_items', ['status', 'due_date'])
    op.create_index('ix_todo_user_status', 'todo_items', ['user_id', 'status'])
    op.create_index('ix_todo_user_priority', 'todo_items', ['user_id', 'priority'])
    op.create_index('ix_todo_source', 'todo_items', ['source_type', 'source_id'])


def downgrade() -> None:
    # Drop indexes
    op.drop_index('ix_todo_source', table_name='todo_items')
    op.drop_index('ix_todo_user_priority', table_name='todo_items')
    op.drop_index('ix_todo_user_status', table_name='todo_items')
    op.drop_index('ix_todo_status_due', table_name='todo_items')
    op.drop_index('ix_todo_items_contact_email', table_name='todo_items')
    op.drop_index('ix_todo_items_source_id', table_name='todo_items')
    op.drop_index('ix_todo_items_due_date', table_name='todo_items')
    op.drop_index('ix_todo_items_status', table_name='todo_items')
    op.drop_index('ix_todo_items_priority', table_name='todo_items')
    op.drop_index('ix_todo_items_category', table_name='todo_items')
    op.drop_index('ix_todo_items_user_id', table_name='todo_items')

    # Drop table
    op.drop_table('todo_items')

    # Drop enums
    op.execute('DROP TYPE IF EXISTS todostatus')
    op.execute('DROP TYPE IF EXISTS todopriority')
    op.execute('DROP TYPE IF EXISTS todocategory')
