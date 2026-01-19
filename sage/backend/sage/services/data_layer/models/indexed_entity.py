"""IndexedEntityModel for storing generic entity types (memory, event, fact)."""

from datetime import datetime

from sqlalchemy import String, DateTime, Text, Index
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import JSONB

from sage.services.database import Base


class IndexedEntityModel(Base):
    """
    Generic indexed entity for types not covered by existing models.

    Used for: memory, event, fact entity types.
    Existing entity types (email, contact, followup, meeting) use their
    dedicated SQLAlchemy models with adapters.
    """

    __tablename__ = "indexed_entities"

    # Primary key: format is {type}_{uuid}
    id: Mapped[str] = mapped_column(String(255), primary_key=True)

    # Entity type: memory, event, fact
    entity_type: Mapped[str] = mapped_column(String(50), index=True, nullable=False)

    # Source of the entity (e.g., "calendar", "agent", "user")
    source: Mapped[str] = mapped_column(String(100), nullable=False)

    # Structured data (raw/parsed data from source)
    structured: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # Analyzed data (AI-generated analysis)
    analyzed: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # Additional metadata
    metadata_: Mapped[dict | None] = mapped_column("metadata", JSONB, nullable=True)

    # Qdrant point ID for vector search
    qdrant_point_id: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Soft delete support
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    __table_args__ = (
        Index("ix_indexed_entities_type_created", "entity_type", "created_at"),
        Index(
            "ix_indexed_entities_structured",
            "structured",
            postgresql_using="gin",
        ),
        Index(
            "ix_indexed_entities_metadata",
            "metadata",
            postgresql_using="gin",
        ),
    )

    @property
    def is_deleted(self) -> bool:
        """Check if entity has been soft deleted."""
        return self.deleted_at is not None

    def soft_delete(self) -> None:
        """Mark entity as soft deleted."""
        self.deleted_at = datetime.utcnow()
