"""Followup adapter for converting between Followup and IndexedEntity."""

from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from sage.agents.base import IndexedEntity
from sage.models.followup import Followup, FollowupStatus, FollowupPriority
from sage.services.data_layer.adapters.base import BaseEntityAdapter


class FollowupAdapter(BaseEntityAdapter[Followup]):
    """Adapter for followup entities stored in followups table."""

    entity_type = "followup"

    def to_indexed_entity(self, model: Followup) -> IndexedEntity:
        """Convert Followup to IndexedEntity."""
        return IndexedEntity(
            id=self.make_entity_id(model.id),
            entity_type=self.entity_type,
            source="database",
            structured={
                "gmail_id": model.gmail_id,
                "thread_id": model.thread_id,
                "subject": model.subject,
                "contact_email": model.contact_email,
                "contact_name": model.contact_name,
                "status": model.status.value if model.status else None,
                "priority": model.priority.value if model.priority else None,
                "due_date": model.due_date.isoformat() if model.due_date else None,
                "escalation_email": model.escalation_email,
                "escalation_days": model.escalation_days,
            },
            analyzed={
                "notes": model.notes,
                "ai_summary": model.ai_summary,
            },
            metadata={
                "db_id": model.id,
                "user_id": model.user_id,
                "email_id": model.email_id,
                "reminder_sent_at": model.reminder_sent_at.isoformat() if model.reminder_sent_at else None,
                "escalated_at": model.escalated_at.isoformat() if model.escalated_at else None,
                "completed_at": model.completed_at.isoformat() if model.completed_at else None,
                "completed_reason": model.completed_reason,
                "created_at": model.created_at.isoformat() if model.created_at else None,
                "updated_at": model.updated_at.isoformat() if model.updated_at else None,
            },
        )

    def from_indexed_entity(self, entity: IndexedEntity) -> dict[str, Any]:
        """Convert IndexedEntity to dict for Followup creation/update."""
        structured = entity.structured
        analyzed = entity.analyzed
        metadata = entity.metadata

        result = {
            "gmail_id": structured.get("gmail_id"),
            "thread_id": structured.get("thread_id"),
            "subject": structured.get("subject"),
            "contact_email": structured.get("contact_email"),
            "contact_name": structured.get("contact_name"),
            "escalation_email": structured.get("escalation_email"),
            "escalation_days": structured.get("escalation_days", 7),
            "notes": analyzed.get("notes"),
            "ai_summary": analyzed.get("ai_summary"),
            "user_id": metadata.get("user_id"),
            "email_id": metadata.get("email_id"),
        }

        # Handle status enum
        if structured.get("status"):
            try:
                result["status"] = FollowupStatus(structured["status"])
            except ValueError:
                result["status"] = FollowupStatus.PENDING

        # Handle priority enum
        if structured.get("priority"):
            try:
                result["priority"] = FollowupPriority(structured["priority"])
            except ValueError:
                result["priority"] = FollowupPriority.NORMAL

        # Handle due_date
        if structured.get("due_date"):
            if isinstance(structured["due_date"], str):
                result["due_date"] = datetime.fromisoformat(structured["due_date"])
            else:
                result["due_date"] = structured["due_date"]

        return result

    async def get_by_id(self, session: AsyncSession, entity_id: str) -> Followup | None:
        """Retrieve Followup by entity ID."""
        db_id = self.parse_entity_id(entity_id)
        try:
            db_id_int = int(db_id)
        except ValueError:
            return None

        result = await session.execute(
            select(Followup).where(Followup.id == db_id_int)
        )
        return result.scalar_one_or_none()

    async def store(self, session: AsyncSession, entity: IndexedEntity) -> str:
        """Store a followup entity (upsert)."""
        data = self.from_indexed_entity(entity)

        # Try to get existing by ID from entity
        db_id = self.parse_entity_id(entity.id)
        model = None

        try:
            db_id_int = int(db_id)
            result = await session.execute(
                select(Followup).where(Followup.id == db_id_int)
            )
            model = result.scalar_one_or_none()
        except ValueError:
            pass

        # Also try to find by gmail_id if not found by ID
        if model is None and data.get("gmail_id"):
            result = await session.execute(
                select(Followup).where(Followup.gmail_id == data["gmail_id"])
            )
            model = result.scalar_one_or_none()

        if model:
            # Update existing
            for key, value in data.items():
                if value is not None:
                    setattr(model, key, value)
        else:
            # Create new - require user_id
            if not data.get("user_id"):
                raise ValueError("Followup must have a user_id")
            model = Followup(**data)
            session.add(model)

        await session.flush()
        return self.make_entity_id(model.id)

    async def delete(self, session: AsyncSession, entity_id: str) -> bool:
        """Delete a followup by entity ID."""
        db_id = self.parse_entity_id(entity_id)
        try:
            db_id_int = int(db_id)
        except ValueError:
            return False

        result = await session.execute(
            select(Followup).where(Followup.id == db_id_int)
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
    ) -> list[Followup]:
        """Query followups with filters."""
        query = select(Followup)

        # Apply filters
        if "user_id" in filters:
            query = query.where(Followup.user_id == filters["user_id"])
        if "status" in filters:
            if isinstance(filters["status"], str):
                try:
                    filters["status"] = FollowupStatus(filters["status"])
                except ValueError:
                    pass
            query = query.where(Followup.status == filters["status"])
        if "contact_email" in filters:
            query = query.where(Followup.contact_email == filters["contact_email"])
        if "due_before" in filters:
            query = query.where(Followup.due_date <= filters["due_before"])
        if "due_after" in filters:
            query = query.where(Followup.due_date >= filters["due_after"])

        query = query.order_by(Followup.due_date.asc()).limit(limit)

        result = await session.execute(query)
        return list(result.scalars().all())

    def get_embedding_text(self, entity: IndexedEntity) -> str:
        """Generate embedding text for followup."""
        structured = entity.structured
        analyzed = entity.analyzed

        parts = []

        # Subject
        if structured.get("subject"):
            parts.append(f"Subject: {structured['subject']}")

        # Contact
        if structured.get("contact_name"):
            parts.append(f"Contact: {structured['contact_name']} <{structured.get('contact_email', '')}>")
        elif structured.get("contact_email"):
            parts.append(f"Contact: {structured['contact_email']}")

        # Status and priority
        if structured.get("status"):
            parts.append(f"Status: {structured['status']}")
        if structured.get("priority"):
            parts.append(f"Priority: {structured['priority']}")

        # Due date
        if structured.get("due_date"):
            parts.append(f"Due: {structured['due_date']}")

        # Notes and summary
        if analyzed.get("notes"):
            parts.append(f"Notes: {analyzed['notes']}")
        if analyzed.get("ai_summary"):
            parts.append(f"Summary: {analyzed['ai_summary']}")

        return "\n".join(parts)
