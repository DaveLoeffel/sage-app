"""EntityRelationship model for storing relationships between entities."""

from datetime import datetime

from sqlalchemy import String, DateTime, Index, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import JSONB

from sage.services.database import Base


class EntityRelationship(Base):
    """
    Relationship between two entities.

    Stores directional relationships with type and metadata.
    Supports any combination of entity types.
    """

    __tablename__ = "entity_relationships"

    id: Mapped[int] = mapped_column(primary_key=True)

    # Source entity
    from_entity_id: Mapped[str] = mapped_column(String(255), index=True, nullable=False)
    from_entity_type: Mapped[str] = mapped_column(String(50), nullable=False)

    # Target entity
    to_entity_id: Mapped[str] = mapped_column(String(255), index=True, nullable=False)
    to_entity_type: Mapped[str] = mapped_column(String(50), nullable=False)

    # Relationship type (e.g., "sent_to", "mentions", "related_to", "follow_up_for")
    relationship_type: Mapped[str] = mapped_column(String(100), index=True, nullable=False)

    # Additional metadata about the relationship
    metadata_: Mapped[dict | None] = mapped_column("metadata", JSONB, nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    __table_args__ = (
        # Unique constraint: only one relationship of each type between two entities
        UniqueConstraint(
            "from_entity_id",
            "to_entity_id",
            "relationship_type",
            name="uq_entity_relationship",
        ),
        Index("ix_entity_rel_from_type", "from_entity_id", "relationship_type"),
        Index("ix_entity_rel_to_type", "to_entity_id", "relationship_type"),
    )
