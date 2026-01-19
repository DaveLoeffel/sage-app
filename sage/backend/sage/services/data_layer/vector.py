"""Multi-entity vector search service using Qdrant."""

import logging
from typing import Any
import uuid

from qdrant_client import QdrantClient
from qdrant_client.http import models
from qdrant_client.http.models import Distance, VectorParams, PointStruct, Filter, FieldCondition, MatchValue
from sentence_transformers import SentenceTransformer

from sage.config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)

# Embedding model - small and fast, 384 dimensions
EMBEDDING_MODEL = "all-MiniLM-L6-v2"
EMBEDDING_DIM = 384

# Collection name for all entities
ENTITIES_COLLECTION = "sage_entities"


class MultiEntityVectorService:
    """
    Service for semantic search across all entity types.

    Uses a single Qdrant collection with entity_type in payload for filtering.
    Supports: email, contact, followup, meeting, memory, event, fact
    """

    def __init__(self):
        self.client = QdrantClient(url=settings.qdrant_url)
        self._model: SentenceTransformer | None = None
        self._ensure_collection()

    @property
    def model(self) -> SentenceTransformer:
        """Lazy load the embedding model."""
        if self._model is None:
            logger.info(f"Loading embedding model: {EMBEDDING_MODEL}")
            self._model = SentenceTransformer(EMBEDDING_MODEL)
        return self._model

    def _ensure_collection(self) -> None:
        """Ensure the entities collection exists."""
        collections = self.client.get_collections().collections
        collection_names = [c.name for c in collections]

        if ENTITIES_COLLECTION not in collection_names:
            logger.info(f"Creating Qdrant collection: {ENTITIES_COLLECTION}")
            self.client.create_collection(
                collection_name=ENTITIES_COLLECTION,
                vectors_config=VectorParams(
                    size=EMBEDDING_DIM,
                    distance=Distance.COSINE,
                ),
            )
            # Create payload index for entity_type filtering
            self.client.create_payload_index(
                collection_name=ENTITIES_COLLECTION,
                field_name="entity_type",
                field_schema=models.PayloadSchemaType.KEYWORD,
            )
            logger.info(f"Collection {ENTITIES_COLLECTION} created with entity_type index")

    def generate_embedding(self, text: str) -> list[float]:
        """Generate embedding for text."""
        if not text or not text.strip():
            return [0.0] * EMBEDDING_DIM
        # Truncate long text to avoid memory issues
        text = text[:8000]
        embedding = self.model.encode(text, convert_to_numpy=True)
        return embedding.tolist()

    def _make_point_id(self, entity_id: str) -> str:
        """Generate a consistent Qdrant point ID from entity ID."""
        return str(uuid.uuid5(uuid.NAMESPACE_DNS, entity_id))

    def index_entity(
        self,
        entity_id: str,
        entity_type: str,
        text: str,
        payload: dict[str, Any] | None = None,
    ) -> str:
        """
        Index an entity in the vector database.

        Args:
            entity_id: Unique entity ID (e.g., "email_abc123")
            entity_type: Type of entity (e.g., "email", "contact")
            text: Text to embed for semantic search
            payload: Additional payload data to store

        Returns:
            The Qdrant point ID
        """
        embedding = self.generate_embedding(text)
        point_id = self._make_point_id(entity_id)

        # Build payload
        point_payload = {
            "entity_id": entity_id,
            "entity_type": entity_type,
            "text_preview": text[:500] if text else "",
        }
        if payload:
            point_payload.update(payload)

        # Upsert the point
        self.client.upsert(
            collection_name=ENTITIES_COLLECTION,
            points=[
                PointStruct(
                    id=point_id,
                    vector=embedding,
                    payload=point_payload,
                )
            ],
        )

        logger.debug(f"Indexed entity {entity_id} ({entity_type}) with point ID {point_id}")
        return point_id

    def search(
        self,
        query: str,
        entity_types: list[str] | None = None,
        limit: int = 10,
        score_threshold: float = 0.3,
    ) -> list[dict[str, Any]]:
        """
        Search for entities similar to the query.

        Args:
            query: Search query text
            entity_types: Optional list of entity types to filter
            limit: Maximum number of results
            score_threshold: Minimum similarity score

        Returns:
            List of search results with entity_id, entity_type, score, and payload
        """
        query_embedding = self.generate_embedding(query)

        # Build filter for entity types
        query_filter = None
        if entity_types:
            if len(entity_types) == 1:
                query_filter = Filter(
                    must=[
                        FieldCondition(
                            key="entity_type",
                            match=MatchValue(value=entity_types[0]),
                        )
                    ]
                )
            else:
                # Multiple entity types - use should (OR)
                query_filter = Filter(
                    should=[
                        FieldCondition(
                            key="entity_type",
                            match=MatchValue(value=et),
                        )
                        for et in entity_types
                    ]
                )

        results = self.client.query_points(
            collection_name=ENTITIES_COLLECTION,
            query=query_embedding,
            query_filter=query_filter,
            limit=limit,
            score_threshold=score_threshold,
        )

        return [
            {
                "entity_id": hit.payload.get("entity_id"),
                "entity_type": hit.payload.get("entity_type"),
                "score": hit.score,
                "text_preview": hit.payload.get("text_preview"),
                **{k: v for k, v in hit.payload.items() if k not in ["entity_id", "entity_type", "text_preview"]},
            }
            for hit in results.points
        ]

    def delete_entity(self, entity_id: str) -> None:
        """Delete an entity from the vector database."""
        point_id = self._make_point_id(entity_id)
        self.client.delete(
            collection_name=ENTITIES_COLLECTION,
            points_selector=models.PointIdsList(points=[point_id]),
        )
        logger.debug(f"Deleted entity {entity_id} (point ID {point_id})")

    def get_entity_point(self, entity_id: str) -> dict[str, Any] | None:
        """Retrieve a specific entity's point data."""
        point_id = self._make_point_id(entity_id)
        try:
            results = self.client.retrieve(
                collection_name=ENTITIES_COLLECTION,
                ids=[point_id],
                with_payload=True,
            )
            if results:
                point = results[0]
                return {
                    "point_id": point_id,
                    "entity_id": point.payload.get("entity_id"),
                    "entity_type": point.payload.get("entity_type"),
                    "payload": point.payload,
                }
        except Exception:
            pass
        return None

    def get_collection_info(self) -> dict[str, Any]:
        """Get information about the collection."""
        info = self.client.get_collection(ENTITIES_COLLECTION)
        return {
            "name": ENTITIES_COLLECTION,
            "points_count": info.points_count,
            "status": str(info.status),
        }

    def count_by_type(self) -> dict[str, int]:
        """Count entities by type."""
        # This is an approximation - Qdrant doesn't have native group by
        # For accurate counts, would need to scroll through all points
        entity_types = ["email", "contact", "followup", "meeting", "memory", "event", "fact"]
        counts = {}

        for et in entity_types:
            result = self.client.count(
                collection_name=ENTITIES_COLLECTION,
                count_filter=Filter(
                    must=[
                        FieldCondition(
                            key="entity_type",
                            match=MatchValue(value=et),
                        )
                    ]
                ),
            )
            counts[et] = result.count

        return counts


# Singleton instance
_multi_vector_service: MultiEntityVectorService | None = None


def get_multi_vector_service() -> MultiEntityVectorService:
    """Get the singleton multi-entity vector search service."""
    global _multi_vector_service
    if _multi_vector_service is None:
        _multi_vector_service = MultiEntityVectorService()
    return _multi_vector_service
