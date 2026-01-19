"""
DataLayerService - Concrete implementation of DataLayerInterface.

Bridges the agent system to the storage infrastructure (PostgreSQL, Qdrant).
"""

import logging
from typing import Any

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from sage.agents.base import (
    DataLayerInterface,
    IndexedEntity,
    SearchResult,
    Relationship,
)
from sage.services.data_layer.adapters.base import BaseEntityAdapter
from sage.services.data_layer.adapters.email import EmailAdapter
from sage.services.data_layer.adapters.contact import ContactAdapter
from sage.services.data_layer.adapters.followup import FollowupAdapter
from sage.services.data_layer.adapters.meeting import MeetingAdapter
from sage.services.data_layer.adapters.generic import GenericAdapter
from sage.services.data_layer.models.relationship import EntityRelationship
from sage.services.data_layer.vector import MultiEntityVectorService, get_multi_vector_service

logger = logging.getLogger(__name__)


class DataLayerService(DataLayerInterface):
    """
    Implementation of DataLayerInterface for the Sage system.

    Provides unified access to:
    - Entity storage across PostgreSQL tables
    - Vector search via Qdrant
    - Relationship management
    """

    # Mapping of entity types to their adapters
    ADAPTER_CLASSES: dict[str, type[BaseEntityAdapter]] = {
        "email": EmailAdapter,
        "contact": ContactAdapter,
        "followup": FollowupAdapter,
        "meeting": MeetingAdapter,
    }

    # Entity types handled by GenericAdapter
    GENERIC_TYPES = {"memory", "event", "fact"}

    def __init__(
        self,
        session: AsyncSession,
        vector_service: MultiEntityVectorService | None = None,
    ):
        """
        Initialize the DataLayerService.

        Args:
            session: AsyncIO SQLAlchemy session for database operations
            vector_service: Optional vector service (uses singleton if not provided)
        """
        self.session = session
        self.vector_service = vector_service or get_multi_vector_service()

        # Initialize adapters
        self._adapters: dict[str, BaseEntityAdapter] = {}
        for entity_type, adapter_class in self.ADAPTER_CLASSES.items():
            self._adapters[entity_type] = adapter_class()

        # Generic adapters for memory/event/fact
        for generic_type in self.GENERIC_TYPES:
            self._adapters[generic_type] = GenericAdapter(generic_type)

    def _get_adapter(self, entity_type: str) -> BaseEntityAdapter:
        """Get the adapter for an entity type."""
        if entity_type in self._adapters:
            return self._adapters[entity_type]

        # For unknown types, use GenericAdapter
        logger.warning(f"Unknown entity type '{entity_type}', using GenericAdapter")
        adapter = GenericAdapter(entity_type)
        self._adapters[entity_type] = adapter
        return adapter

    def _parse_entity_type(self, entity_id: str) -> str:
        """Extract entity type from entity ID."""
        if "_" in entity_id:
            return entity_id.split("_", 1)[0]
        raise ValueError(f"Invalid entity ID format: {entity_id}")

    # =========================================================================
    # Write Operations
    # =========================================================================

    async def store_entity(self, entity: IndexedEntity) -> str:
        """
        Store an entity and index in vector database.

        Args:
            entity: The IndexedEntity to store

        Returns:
            The entity ID
        """
        adapter = self._get_adapter(entity.entity_type)

        # Store in PostgreSQL
        entity_id = await adapter.store(self.session, entity)

        # Update entity ID if it was generated
        if entity.id != entity_id:
            entity.id = entity_id

        # Index in Qdrant
        embedding_text = adapter.get_embedding_text(entity)
        if embedding_text:
            payload = {
                "source": entity.source,
            }
            # Add key structured fields to payload for filtering
            if entity.structured:
                for key in ["subject", "title", "name", "email"]:
                    if key in entity.structured:
                        payload[key] = entity.structured[key]

            point_id = self.vector_service.index_entity(
                entity_id=entity_id,
                entity_type=entity.entity_type,
                text=embedding_text,
                payload=payload,
            )

            # Update entity with qdrant reference
            entity.metadata["qdrant_point_id"] = point_id

        logger.info(f"Stored entity {entity_id} ({entity.entity_type})")
        return entity_id

    async def update_entity(self, entity_id: str, updates: dict) -> bool:
        """
        Update an existing entity.

        Args:
            entity_id: The entity ID to update
            updates: Dict of fields to update (can include structured, analyzed, metadata)

        Returns:
            True if updated, False if not found
        """
        entity_type = self._parse_entity_type(entity_id)
        adapter = self._get_adapter(entity_type)

        # Get existing entity
        model = await adapter.get_by_id(self.session, entity_id)
        if not model:
            return False

        # Convert to IndexedEntity and apply updates
        entity = adapter.to_indexed_entity(model)

        # Merge updates
        if "structured" in updates:
            entity.structured.update(updates["structured"])
        if "analyzed" in updates:
            entity.analyzed.update(updates["analyzed"])
        if "metadata" in updates:
            entity.metadata.update(updates["metadata"])

        # Store updated entity
        await adapter.store(self.session, entity)

        # Re-index in Qdrant
        embedding_text = adapter.get_embedding_text(entity)
        if embedding_text:
            self.vector_service.index_entity(
                entity_id=entity_id,
                entity_type=entity_type,
                text=embedding_text,
            )

        logger.info(f"Updated entity {entity_id}")
        return True

    async def delete_entity(self, entity_id: str) -> bool:
        """
        Delete an entity from all stores.

        Args:
            entity_id: The entity ID to delete

        Returns:
            True if deleted, False if not found
        """
        entity_type = self._parse_entity_type(entity_id)
        adapter = self._get_adapter(entity_type)

        # Delete from PostgreSQL
        deleted = await adapter.delete(self.session, entity_id)

        # Delete from Qdrant
        try:
            self.vector_service.delete_entity(entity_id)
        except Exception as e:
            logger.warning(f"Error deleting from Qdrant: {e}")

        # Delete relationships
        await self._delete_entity_relationships(entity_id)

        if deleted:
            logger.info(f"Deleted entity {entity_id}")
        return deleted

    async def _delete_entity_relationships(self, entity_id: str) -> None:
        """Delete all relationships involving an entity."""
        result = await self.session.execute(
            select(EntityRelationship).where(
                (EntityRelationship.from_entity_id == entity_id)
                | (EntityRelationship.to_entity_id == entity_id)
            )
        )
        relationships = result.scalars().all()
        for rel in relationships:
            await self.session.delete(rel)

    async def create_relationship(
        self,
        from_id: str,
        to_id: str,
        rel_type: str,
        metadata: dict | None = None,
    ) -> bool:
        """
        Create a relationship between two entities.

        Args:
            from_id: Source entity ID
            to_id: Target entity ID
            rel_type: Relationship type (e.g., "sent_to", "mentions")
            metadata: Optional relationship metadata

        Returns:
            True if created, False if already exists
        """
        from_type = self._parse_entity_type(from_id)
        to_type = self._parse_entity_type(to_id)

        # Check if relationship already exists
        existing = await self.session.execute(
            select(EntityRelationship).where(
                and_(
                    EntityRelationship.from_entity_id == from_id,
                    EntityRelationship.to_entity_id == to_id,
                    EntityRelationship.relationship_type == rel_type,
                )
            )
        )
        if existing.scalar_one_or_none():
            # Update metadata if provided
            if metadata:
                rel = existing.scalar_one()
                rel.metadata_ = metadata
                return True
            return False

        # Create new relationship
        relationship = EntityRelationship(
            from_entity_id=from_id,
            from_entity_type=from_type,
            to_entity_id=to_id,
            to_entity_type=to_type,
            relationship_type=rel_type,
            metadata_=metadata,
        )
        self.session.add(relationship)

        logger.debug(f"Created relationship: {from_id} --{rel_type}--> {to_id}")
        return True

    # =========================================================================
    # Read Operations
    # =========================================================================

    async def get_entity(self, entity_id: str) -> IndexedEntity | None:
        """
        Retrieve a single entity by ID.

        Args:
            entity_id: The entity ID to retrieve

        Returns:
            IndexedEntity or None if not found
        """
        entity_type = self._parse_entity_type(entity_id)
        adapter = self._get_adapter(entity_type)

        model = await adapter.get_by_id(self.session, entity_id)
        if not model:
            return None

        entity = adapter.to_indexed_entity(model)

        # Enrich with relationships
        relationships = await self.get_relationships(entity_id)
        entity.relationships = {
            "outgoing": [
                {"to": r.to_id, "type": r.rel_type, "metadata": r.metadata}
                for r in relationships
                if r.from_id == entity_id
            ],
            "incoming": [
                {"from": r.from_id, "type": r.rel_type, "metadata": r.metadata}
                for r in relationships
                if r.to_id == entity_id
            ],
        }

        return entity

    async def vector_search(
        self,
        query: str,
        entity_types: list[str] | None = None,
        limit: int = 10,
    ) -> list[SearchResult]:
        """
        Perform semantic search across entity embeddings.

        Args:
            query: Search query text
            entity_types: Optional list of entity types to filter
            limit: Maximum number of results

        Returns:
            List of SearchResult with entities and scores
        """
        # Search Qdrant
        results = self.vector_service.search(
            query=query,
            entity_types=entity_types,
            limit=limit,
        )

        # Hydrate results with full entities
        search_results = []
        for hit in results:
            entity_id = hit.get("entity_id")
            if not entity_id:
                continue

            entity = await self.get_entity(entity_id)
            if entity:
                search_results.append(
                    SearchResult(
                        entity=entity,
                        score=hit.get("score", 0.0),
                        match_type="semantic",
                    )
                )

        return search_results

    async def structured_query(
        self,
        filters: dict,
        entity_type: str,
        limit: int = 100,
    ) -> list[IndexedEntity]:
        """
        Query entities by structured fields.

        Args:
            filters: Filter conditions (adapter-specific)
            entity_type: Type of entity to query
            limit: Maximum number of results

        Returns:
            List of matching IndexedEntity objects
        """
        adapter = self._get_adapter(entity_type)

        models = await adapter.query(self.session, filters, limit)

        return [adapter.to_indexed_entity(model) for model in models]

    async def get_relationships(
        self,
        entity_id: str,
        rel_types: list[str] | None = None,
    ) -> list[Relationship]:
        """
        Get relationships for an entity.

        Args:
            entity_id: The entity ID
            rel_types: Optional list of relationship types to filter

        Returns:
            List of Relationship objects
        """
        query = select(EntityRelationship).where(
            (EntityRelationship.from_entity_id == entity_id)
            | (EntityRelationship.to_entity_id == entity_id)
        )

        if rel_types:
            query = query.where(EntityRelationship.relationship_type.in_(rel_types))

        result = await self.session.execute(query)
        models = result.scalars().all()

        return [
            Relationship(
                from_id=m.from_entity_id,
                to_id=m.to_entity_id,
                rel_type=m.relationship_type,
                metadata=m.metadata_ or {},
            )
            for m in models
        ]

    # =========================================================================
    # Convenience Methods (not part of DataLayerInterface)
    # =========================================================================

    async def get_entities_by_type(
        self,
        entity_type: str,
        limit: int = 100,
    ) -> list[IndexedEntity]:
        """Get all entities of a specific type."""
        return await self.structured_query({}, entity_type, limit)

    async def search_and_filter(
        self,
        query: str,
        entity_types: list[str] | None = None,
        filters: dict[str, Any] | None = None,
        limit: int = 10,
    ) -> list[SearchResult]:
        """
        Combined semantic search with structured filtering.

        First performs vector search, then filters results by structured criteria.
        """
        # Get more results from vector search to allow for filtering
        vector_limit = limit * 3
        results = await self.vector_search(query, entity_types, vector_limit)

        if not filters:
            return results[:limit]

        # Apply structured filters
        filtered = []
        for result in results:
            entity = result.entity
            matches = True

            for key, value in filters.items():
                if key in entity.structured:
                    if entity.structured[key] != value:
                        matches = False
                        break
                elif key in entity.analyzed:
                    if entity.analyzed[key] != value:
                        matches = False
                        break

            if matches:
                filtered.append(result)
                if len(filtered) >= limit:
                    break

        return filtered

    async def get_related_entities(
        self,
        entity_id: str,
        rel_types: list[str] | None = None,
        direction: str = "both",
    ) -> list[IndexedEntity]:
        """
        Get entities related to the given entity.

        Args:
            entity_id: The source entity ID
            rel_types: Optional relationship types to filter
            direction: "outgoing", "incoming", or "both"

        Returns:
            List of related entities
        """
        relationships = await self.get_relationships(entity_id, rel_types)

        related_ids = set()
        for rel in relationships:
            if direction in ("outgoing", "both") and rel.from_id == entity_id:
                related_ids.add(rel.to_id)
            if direction in ("incoming", "both") and rel.to_id == entity_id:
                related_ids.add(rel.from_id)

        # Fetch related entities
        entities = []
        for related_id in related_ids:
            entity = await self.get_entity(related_id)
            if entity:
                entities.append(entity)

        return entities

    def get_collection_stats(self) -> dict[str, Any]:
        """Get statistics about the vector collection."""
        info = self.vector_service.get_collection_info()
        counts = self.vector_service.count_by_type()
        return {
            **info,
            "counts_by_type": counts,
        }
