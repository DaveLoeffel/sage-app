"""Vector search service using Qdrant and sentence-transformers."""

import logging
from typing import Any
import uuid

from qdrant_client import QdrantClient
from qdrant_client.http import models
from qdrant_client.http.models import Distance, VectorParams, PointStruct
from sentence_transformers import SentenceTransformer

from sage.config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)

# Embedding model - small and fast, 384 dimensions
EMBEDDING_MODEL = "all-MiniLM-L6-v2"
EMBEDDING_DIM = 384


class VectorSearchService:
    """Service for semantic search using Qdrant vector database."""

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
        """Ensure the emails collection exists."""
        collections = self.client.get_collections().collections
        collection_names = [c.name for c in collections]

        if settings.qdrant_collection not in collection_names:
            logger.info(f"Creating Qdrant collection: {settings.qdrant_collection}")
            self.client.create_collection(
                collection_name=settings.qdrant_collection,
                vectors_config=VectorParams(
                    size=EMBEDDING_DIM,
                    distance=Distance.COSINE,
                ),
            )
            logger.info(f"Collection {settings.qdrant_collection} created")

    def generate_embedding(self, text: str) -> list[float]:
        """Generate embedding for text."""
        if not text or not text.strip():
            return [0.0] * EMBEDDING_DIM
        # Truncate long text to avoid memory issues
        text = text[:8000]
        embedding = self.model.encode(text, convert_to_numpy=True)
        return embedding.tolist()

    def index_email(
        self,
        email_id: int,
        gmail_id: str,
        subject: str,
        body: str | None,
        sender: str,
        received_at: str,
    ) -> str:
        """Index an email in the vector database."""
        # Create searchable text combining subject and body
        searchable_text = f"Subject: {subject}\n\nFrom: {sender}\n\n{body or ''}"
        embedding = self.generate_embedding(searchable_text)

        # Generate a UUID for Qdrant
        point_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, gmail_id))

        # Upsert the point
        self.client.upsert(
            collection_name=settings.qdrant_collection,
            points=[
                PointStruct(
                    id=point_id,
                    vector=embedding,
                    payload={
                        "email_id": email_id,
                        "gmail_id": gmail_id,
                        "subject": subject,
                        "sender": sender,
                        "received_at": received_at,
                        "text_preview": searchable_text[:500],
                    },
                )
            ],
        )

        logger.debug(f"Indexed email {gmail_id} with point ID {point_id}")
        return point_id

    def search(
        self,
        query: str,
        limit: int = 10,
        score_threshold: float = 0.3,
    ) -> list[dict[str, Any]]:
        """Search for emails similar to the query."""
        query_embedding = self.generate_embedding(query)

        results = self.client.query_points(
            collection_name=settings.qdrant_collection,
            query=query_embedding,
            limit=limit,
            score_threshold=score_threshold,
        )

        return [
            {
                "email_id": hit.payload.get("email_id"),
                "gmail_id": hit.payload.get("gmail_id"),
                "subject": hit.payload.get("subject"),
                "sender": hit.payload.get("sender"),
                "received_at": hit.payload.get("received_at"),
                "score": hit.score,
                "text_preview": hit.payload.get("text_preview"),
            }
            for hit in results.points
        ]

    def delete_email(self, gmail_id: str) -> None:
        """Delete an email from the vector database."""
        point_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, gmail_id))
        self.client.delete(
            collection_name=settings.qdrant_collection,
            points_selector=models.PointIdsList(points=[point_id]),
        )

    def get_collection_info(self) -> dict[str, Any]:
        """Get information about the collection."""
        info = self.client.get_collection(settings.qdrant_collection)
        return {
            "name": settings.qdrant_collection,
            "points_count": info.points_count,
            "status": str(info.status),
        }


# Singleton instance
_vector_service: VectorSearchService | None = None


def get_vector_service() -> VectorSearchService:
    """Get the singleton vector search service."""
    global _vector_service
    if _vector_service is None:
        _vector_service = VectorSearchService()
    return _vector_service
