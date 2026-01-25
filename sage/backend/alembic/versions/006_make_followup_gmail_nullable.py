"""Make followup gmail_id and thread_id nullable for meeting-based followups.

Revision ID: 006
Revises: 005
Create Date: 2026-01-20

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '006'
down_revision: Union[str, None] = '005'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Make gmail_id nullable to support meeting-based followups
    op.alter_column(
        'followups',
        'gmail_id',
        existing_type=sa.String(255),
        nullable=True
    )

    # Make thread_id nullable to support meeting-based followups
    op.alter_column(
        'followups',
        'thread_id',
        existing_type=sa.String(255),
        nullable=True
    )

    # Add source_type column to track where the followup came from
    op.add_column(
        'followups',
        sa.Column('source_type', sa.String(50), nullable=True, server_default='email')
    )

    # Add source_id column to track meeting ID or other source
    op.add_column(
        'followups',
        sa.Column('source_id', sa.String(255), nullable=True)
    )

    # Create index for source tracking
    op.create_index('ix_followups_source', 'followups', ['source_type', 'source_id'])


def downgrade() -> None:
    # Drop source columns
    op.drop_index('ix_followups_source', table_name='followups')
    op.drop_column('followups', 'source_id')
    op.drop_column('followups', 'source_type')

    # Make gmail_id not nullable again
    op.alter_column(
        'followups',
        'gmail_id',
        existing_type=sa.String(255),
        nullable=False
    )

    # Make thread_id not nullable again
    op.alter_column(
        'followups',
        'thread_id',
        existing_type=sa.String(255),
        nullable=False
    )
