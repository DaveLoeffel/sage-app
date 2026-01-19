"""Generic adapter for memory, event, and fact entities."""

from datetime import datetime
from typing import Any
import uuid

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from sage.agents.base import IndexedEntity
from sage.services.data_layer.models.indexed_entity import IndexedEntityModel
from sage.services.data_layer.adapters.base import BaseEntityAdapter


class GenericAdapter(BaseEntityAdapter[IndexedEntityModel]):
    """
    Adapter for generic entity types stored in indexed_entities table.

    Handles: memory, event, fact entity types.
    """

    def __init__(self, entity_type: str):
        """
        Initialize adapter for a specific entity type.

        Args:
            entity_type: The entity type to handle (memory, event, fact)
        """
        self.entity_type = entity_type

    def to_indexed_entity(self, model: IndexedEntityModel) -> IndexedEntity:
        """Convert IndexedEntityModel to IndexedEntity."""
        return IndexedEntity(
            id=model.id,
            entity_type=model.entity_type,
            source=model.source,
            structured=model.structured or {},
            analyzed=model.analyzed or {},
            metadata={
                **(model.metadata_ or {}),
                "qdrant_point_id": model.qdrant_point_id,
                "created_at": model.created_at.isoformat() if model.created_at else None,
                "updated_at": model.updated_at.isoformat() if model.updated_at else None,
            },
        )

    def from_indexed_entity(self, entity: IndexedEntity) -> dict[str, Any]:
        """Convert IndexedEntity to dict for IndexedEntityModel creation/update."""
        # Extract qdrant_point_id from metadata if present
        metadata = dict(entity.metadata) if entity.metadata else {}
        qdrant_point_id = metadata.pop("qdrant_point_id", None)
        metadata.pop("created_at", None)
        metadata.pop("updated_at", None)

        return {
            "id": entity.id,
            "entity_type": entity.entity_type,
            "source": entity.source,
            "structured": entity.structured,
            "analyzed": entity.analyzed,
            "metadata_": metadata if metadata else None,
            "qdrant_point_id": qdrant_point_id,
        }

    async def get_by_id(self, session: AsyncSession, entity_id: str) -> IndexedEntityModel | None:
        """Retrieve IndexedEntityModel by entity ID."""
        result = await session.execute(
            select(IndexedEntityModel).where(
                and_(
                    IndexedEntityModel.id == entity_id,
                    IndexedEntityModel.deleted_at.is_(None),
                )
            )
        )
        return result.scalar_one_or_none()

    async def store(self, session: AsyncSession, entity: IndexedEntity) -> str:
        """Store a generic entity (upsert)."""
        # Generate ID if not provided
        if not entity.id or entity.id == f"{self.entity_type}_":
            entity.id = f"{self.entity_type}_{uuid.uuid4()}"

        data = self.from_indexed_entity(entity)

        # Check if exists (and not deleted)
        existing = await session.execute(
            select(IndexedEntityModel).where(IndexedEntityModel.id == entity.id)
        )
        model = existing.scalar_one_or_none()

        if model:
            # Update existing (even if soft-deleted, revive it)
            model.entity_type = data["entity_type"]
            model.source = data["source"]
            model.structured = data["structured"]
            model.analyzed = data["analyzed"]
            model.metadata_ = data["metadata_"]
            model.qdrant_point_id = data["qdrant_point_id"]
            model.deleted_at = None  # Revive if soft-deleted
            model.updated_at = datetime.utcnow()
        else:
            # Create new
            model = IndexedEntityModel(**data)
            session.add(model)

        await session.flush()
        return model.id

    async def delete(self, session: AsyncSession, entity_id: str) -> bool:
        """Soft delete an entity by ID."""
        result = await session.execute(
            select(IndexedEntityModel).where(
                and_(
                    IndexedEntityModel.id == entity_id,
                    IndexedEntityModel.deleted_at.is_(None),
                )
            )
        )
        model = result.scalar_one_or_none()
        if model:
            model.soft_delete()
            return True
        return False

    async def hard_delete(self, session: AsyncSession, entity_id: str) -> bool:
        """Permanently delete an entity by ID."""
        result = await session.execute(
            select(IndexedEntityModel).where(IndexedEntityModel.id == entity_id)
        )
        model = result.scalar_one_or_none()
        if model:
            await session.delete(model)
            return True
        return False

    async def query(
        self,
        session: AsyncSession,
        filters: dict[str, Any],
        limit: int = 100,
    ) -> list[IndexedEntityModel]:
        """Query entities with filters."""
        query = select(IndexedEntityModel).where(
            and_(
                IndexedEntityModel.entity_type == self.entity_type,
                IndexedEntityModel.deleted_at.is_(None),
            )
        )

        # Apply filters
        if "source" in filters:
            query = query.where(IndexedEntityModel.source == filters["source"])

        # JSONB filters for structured data
        if "structured" in filters and isinstance(filters["structured"], dict):
            for key, value in filters["structured"].items():
                query = query.where(
                    IndexedEntityModel.structured[key].astext == str(value)
                )

        # JSONB filters for metadata
        if "metadata" in filters and isinstance(filters["metadata"], dict):
            for key, value in filters["metadata"].items():
                query = query.where(
                    IndexedEntityModel.metadata_[key].astext == str(value)
                )

        query = query.order_by(IndexedEntityModel.created_at.desc()).limit(limit)

        result = await session.execute(query)
        return list(result.scalars().all())

    def get_embedding_text(self, entity: IndexedEntity) -> str:
        """Generate embedding text for generic entity."""
        parts = []

        # Entity type
        parts.append(f"Type: {entity.entity_type}")

        # Source
        if entity.source:
            parts.append(f"Source: {entity.source}")

        # Structured data - extract key fields
        structured = entity.structured or {}
        for key in ["title", "name", "description", "content", "summary", "text"]:
            if key in structured and structured[key]:
                parts.append(f"{key.capitalize()}: {structured[key]}")

        # Analyzed data
        analyzed = entity.analyzed or {}
        for key in ["summary", "analysis", "context", "notes"]:
            if key in analyzed and analyzed[key]:
                parts.append(f"{key.capitalize()}: {analyzed[key]}")

        return "\n".join(parts)


# Pre-configured adapters for common generic types
class MemoryAdapter(GenericAdapter):
    """Adapter for memory entities."""

    def __init__(self):
        super().__init__("memory")


class EventAdapter(GenericAdapter):
    """Adapter for event entities."""

    def __init__(self):
        super().__init__("event")


class FactAdapter(GenericAdapter):
    """Adapter for fact entities."""

    def __init__(self):
        super().__init__("fact")
