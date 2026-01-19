"""Base adapter for entity conversion between SQLAlchemy models and IndexedEntity."""

from abc import ABC, abstractmethod
from typing import TypeVar, Generic, Any

from sqlalchemy.ext.asyncio import AsyncSession

from sage.agents.base import IndexedEntity

# Type variable for the SQLAlchemy model
T = TypeVar("T")


class BaseEntityAdapter(ABC, Generic[T]):
    """
    Abstract base class for entity adapters.

    Each adapter converts between a specific SQLAlchemy model and IndexedEntity.
    Adapters handle:
    - Conversion to/from IndexedEntity
    - Database CRUD operations
    - Generating embedding text for vector search
    """

    # Entity type this adapter handles (e.g., "email", "contact")
    entity_type: str

    @abstractmethod
    def to_indexed_entity(self, model: T) -> IndexedEntity:
        """
        Convert a SQLAlchemy model to IndexedEntity.

        Args:
            model: The SQLAlchemy model instance

        Returns:
            IndexedEntity representation
        """
        pass

    @abstractmethod
    def from_indexed_entity(self, entity: IndexedEntity) -> dict[str, Any]:
        """
        Convert IndexedEntity to a dict suitable for model creation/update.

        Args:
            entity: The IndexedEntity to convert

        Returns:
            Dict of fields for model creation
        """
        pass

    @abstractmethod
    async def get_by_id(self, session: AsyncSession, entity_id: str) -> T | None:
        """
        Retrieve a model by its entity ID.

        Args:
            session: Database session
            entity_id: The entity ID (format: {type}_{source_id})

        Returns:
            The model instance or None if not found
        """
        pass

    @abstractmethod
    async def store(self, session: AsyncSession, entity: IndexedEntity) -> str:
        """
        Store an entity (upsert).

        Args:
            session: Database session
            entity: The entity to store

        Returns:
            The entity ID
        """
        pass

    @abstractmethod
    async def delete(self, session: AsyncSession, entity_id: str) -> bool:
        """
        Delete an entity by ID.

        Args:
            session: Database session
            entity_id: The entity ID to delete

        Returns:
            True if deleted, False if not found
        """
        pass

    @abstractmethod
    async def query(
        self,
        session: AsyncSession,
        filters: dict[str, Any],
        limit: int = 100,
    ) -> list[T]:
        """
        Query entities with filters.

        Args:
            session: Database session
            filters: Filter conditions
            limit: Maximum results to return

        Returns:
            List of matching models
        """
        pass

    @abstractmethod
    def get_embedding_text(self, entity: IndexedEntity) -> str:
        """
        Generate text for vector embedding.

        Args:
            entity: The entity to generate embedding text for

        Returns:
            Text suitable for embedding generation
        """
        pass

    def parse_entity_id(self, entity_id: str) -> str:
        """
        Extract the source ID from an entity ID.

        Args:
            entity_id: Full entity ID (e.g., "email_abc123")

        Returns:
            The source ID portion (e.g., "abc123")
        """
        prefix = f"{self.entity_type}_"
        if entity_id.startswith(prefix):
            return entity_id[len(prefix):]
        return entity_id

    def make_entity_id(self, source_id: str | int) -> str:
        """
        Create a full entity ID from a source ID.

        Args:
            source_id: The source-specific ID

        Returns:
            Full entity ID (e.g., "email_abc123")
        """
        return f"{self.entity_type}_{source_id}"
