"""Extend picture column to text

Revision ID: 002
Revises: 001
Create Date: 2026-01-16

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '002'
down_revision: Union[str, None] = '001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Change picture column from varchar(500) to text to accommodate long Google URLs
    op.alter_column(
        'users',
        'picture',
        type_=sa.Text(),
        existing_type=sa.String(length=500),
        existing_nullable=True
    )


def downgrade() -> None:
    op.alter_column(
        'users',
        'picture',
        type_=sa.String(length=500),
        existing_type=sa.Text(),
        existing_nullable=True
    )
