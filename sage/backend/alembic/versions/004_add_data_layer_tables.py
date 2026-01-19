"""Add data layer tables for generic entities and relationships

Revision ID: 004
Revises: 003
Create Date: 2026-01-18

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '004'
down_revision: Union[str, None] = '003'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create indexed_entities table for generic entity types (memory, event, fact)
    op.create_table(
        'indexed_entities',
        sa.Column('id', sa.String(length=255), nullable=False),
        sa.Column('entity_type', sa.String(length=50), nullable=False),
        sa.Column('source', sa.String(length=100), nullable=False),
        sa.Column('structured', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('analyzed', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('qdrant_point_id', sa.String(length=255), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('deleted_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )

    # Indexes for indexed_entities
    op.create_index('ix_indexed_entities_entity_type', 'indexed_entities', ['entity_type'], unique=False)
    op.create_index('ix_indexed_entities_type_created', 'indexed_entities', ['entity_type', 'created_at'], unique=False)

    # GIN indexes for JSONB columns
    op.create_index(
        'ix_indexed_entities_structured',
        'indexed_entities',
        ['structured'],
        unique=False,
        postgresql_using='gin'
    )
    op.create_index(
        'ix_indexed_entities_metadata',
        'indexed_entities',
        ['metadata'],
        unique=False,
        postgresql_using='gin'
    )

    # Create entity_relationships table
    op.create_table(
        'entity_relationships',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('from_entity_id', sa.String(length=255), nullable=False),
        sa.Column('from_entity_type', sa.String(length=50), nullable=False),
        sa.Column('to_entity_id', sa.String(length=255), nullable=False),
        sa.Column('to_entity_type', sa.String(length=50), nullable=False),
        sa.Column('relationship_type', sa.String(length=100), nullable=False),
        sa.Column('metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('from_entity_id', 'to_entity_id', 'relationship_type', name='uq_entity_relationship')
    )

    # Indexes for entity_relationships
    op.create_index('ix_entity_rel_from_entity_id', 'entity_relationships', ['from_entity_id'], unique=False)
    op.create_index('ix_entity_rel_to_entity_id', 'entity_relationships', ['to_entity_id'], unique=False)
    op.create_index('ix_entity_rel_relationship_type', 'entity_relationships', ['relationship_type'], unique=False)
    op.create_index('ix_entity_rel_from_type', 'entity_relationships', ['from_entity_id', 'relationship_type'], unique=False)
    op.create_index('ix_entity_rel_to_type', 'entity_relationships', ['to_entity_id', 'relationship_type'], unique=False)


def downgrade() -> None:
    # Drop entity_relationships indexes and table
    op.drop_index('ix_entity_rel_to_type', table_name='entity_relationships')
    op.drop_index('ix_entity_rel_from_type', table_name='entity_relationships')
    op.drop_index('ix_entity_rel_relationship_type', table_name='entity_relationships')
    op.drop_index('ix_entity_rel_to_entity_id', table_name='entity_relationships')
    op.drop_index('ix_entity_rel_from_entity_id', table_name='entity_relationships')
    op.drop_table('entity_relationships')

    # Drop indexed_entities indexes and table
    op.drop_index('ix_indexed_entities_metadata', table_name='indexed_entities', postgresql_using='gin')
    op.drop_index('ix_indexed_entities_structured', table_name='indexed_entities', postgresql_using='gin')
    op.drop_index('ix_indexed_entities_type_created', table_name='indexed_entities')
    op.drop_index('ix_indexed_entities_entity_type', table_name='indexed_entities')
    op.drop_table('indexed_entities')
