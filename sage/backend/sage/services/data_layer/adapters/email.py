"""Email adapter for converting between EmailCache and IndexedEntity."""

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from sage.agents.base import IndexedEntity
from sage.models.email import EmailCache
from sage.services.data_layer.adapters.base import BaseEntityAdapter


class EmailAdapter(BaseEntityAdapter[EmailCache]):
    """Adapter for email entities stored in email_cache table."""

    entity_type = "email"

    def to_indexed_entity(self, model: EmailCache) -> IndexedEntity:
        """Convert EmailCache to IndexedEntity."""
        return IndexedEntity(
            id=self.make_entity_id(model.gmail_id),
            entity_type=self.entity_type,
            source="gmail",
            structured={
                "gmail_id": model.gmail_id,
                "thread_id": model.thread_id,
                "subject": model.subject,
                "sender_email": model.sender_email,
                "sender_name": model.sender_name,
                "to_emails": model.to_emails,
                "cc_emails": model.cc_emails,
                "body_text": model.body_text,
                "snippet": model.snippet,
                "labels": model.labels,
                "is_unread": model.is_unread,
                "has_attachments": model.has_attachments,
                "received_at": model.received_at.isoformat() if model.received_at else None,
            },
            analyzed={
                "category": model.category.value if model.category else None,
                "priority": model.priority.value if model.priority else None,
                "summary": model.summary,
                "action_items": model.action_items,
                "sentiment": model.sentiment,
                "requires_response": model.requires_response,
            },
            metadata={
                "db_id": model.id,
                "history_id": model.history_id,
                "qdrant_id": model.qdrant_id,
                "synced_at": model.synced_at.isoformat() if model.synced_at else None,
                "analyzed_at": model.analyzed_at.isoformat() if model.analyzed_at else None,
            },
        )

    def from_indexed_entity(self, entity: IndexedEntity) -> dict[str, Any]:
        """Convert IndexedEntity to dict for EmailCache creation/update."""
        structured = entity.structured
        analyzed = entity.analyzed
        metadata = entity.metadata

        return {
            "gmail_id": structured.get("gmail_id"),
            "thread_id": structured.get("thread_id"),
            "subject": structured.get("subject"),
            "sender_email": structured.get("sender_email"),
            "sender_name": structured.get("sender_name"),
            "to_emails": structured.get("to_emails"),
            "cc_emails": structured.get("cc_emails"),
            "body_text": structured.get("body_text"),
            "snippet": structured.get("snippet"),
            "labels": structured.get("labels"),
            "is_unread": structured.get("is_unread", True),
            "has_attachments": structured.get("has_attachments", False),
            "category": analyzed.get("category"),
            "priority": analyzed.get("priority"),
            "summary": analyzed.get("summary"),
            "action_items": analyzed.get("action_items"),
            "sentiment": analyzed.get("sentiment"),
            "requires_response": analyzed.get("requires_response"),
            "qdrant_id": metadata.get("qdrant_id"),
        }

    async def get_by_id(self, session: AsyncSession, entity_id: str) -> EmailCache | None:
        """Retrieve EmailCache by entity ID."""
        gmail_id = self.parse_entity_id(entity_id)
        result = await session.execute(
            select(EmailCache).where(EmailCache.gmail_id == gmail_id)
        )
        return result.scalar_one_or_none()

    async def store(self, session: AsyncSession, entity: IndexedEntity) -> str:
        """Store an email entity (upsert)."""
        gmail_id = self.parse_entity_id(entity.id)

        # Check if exists
        existing = await session.execute(
            select(EmailCache).where(EmailCache.gmail_id == gmail_id)
        )
        model = existing.scalar_one_or_none()

        data = self.from_indexed_entity(entity)

        if model:
            # Update existing
            for key, value in data.items():
                if value is not None:
                    setattr(model, key, value)
        else:
            # Create new
            model = EmailCache(**data)
            session.add(model)

        await session.flush()
        return entity.id

    async def delete(self, session: AsyncSession, entity_id: str) -> bool:
        """Delete an email by entity ID."""
        gmail_id = self.parse_entity_id(entity_id)
        result = await session.execute(
            select(EmailCache).where(EmailCache.gmail_id == gmail_id)
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
    ) -> list[EmailCache]:
        """Query emails with filters."""
        query = select(EmailCache)

        # Apply filters
        if "sender_email" in filters:
            query = query.where(EmailCache.sender_email == filters["sender_email"])
        if "is_unread" in filters:
            query = query.where(EmailCache.is_unread == filters["is_unread"])
        if "category" in filters:
            query = query.where(EmailCache.category == filters["category"])
        if "thread_id" in filters:
            query = query.where(EmailCache.thread_id == filters["thread_id"])
        if "received_after" in filters:
            query = query.where(EmailCache.received_at >= filters["received_after"])
        if "received_before" in filters:
            query = query.where(EmailCache.received_at <= filters["received_before"])

        query = query.order_by(EmailCache.received_at.desc()).limit(limit)

        result = await session.execute(query)
        return list(result.scalars().all())

    def get_embedding_text(self, entity: IndexedEntity) -> str:
        """Generate embedding text for email."""
        structured = entity.structured
        analyzed = entity.analyzed

        parts = []

        # Subject
        if structured.get("subject"):
            parts.append(f"Subject: {structured['subject']}")

        # Sender
        if structured.get("sender_name"):
            parts.append(f"From: {structured['sender_name']} <{structured.get('sender_email', '')}>")
        elif structured.get("sender_email"):
            parts.append(f"From: {structured['sender_email']}")

        # Summary (if analyzed)
        if analyzed.get("summary"):
            parts.append(f"Summary: {analyzed['summary']}")

        # Body (truncated)
        if structured.get("body_text"):
            body = structured["body_text"][:2000]
            parts.append(body)

        return "\n\n".join(parts)
