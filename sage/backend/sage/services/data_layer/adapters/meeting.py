"""Meeting adapter for converting between MeetingNote and IndexedEntity."""

from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from sage.agents.base import IndexedEntity
from sage.models.meeting import MeetingNote
from sage.services.data_layer.adapters.base import BaseEntityAdapter


class MeetingAdapter(BaseEntityAdapter[MeetingNote]):
    """Adapter for meeting entities stored in meeting_notes table."""

    entity_type = "meeting"

    def to_indexed_entity(self, model: MeetingNote) -> IndexedEntity:
        """Convert MeetingNote to IndexedEntity."""
        return IndexedEntity(
            id=self.make_entity_id(model.fireflies_id),
            entity_type=self.entity_type,
            source="fireflies",
            structured={
                "fireflies_id": model.fireflies_id,
                "title": model.title,
                "meeting_date": model.meeting_date.isoformat() if model.meeting_date else None,
                "duration_minutes": model.duration_minutes,
                "participants": model.participants,
                "transcript": model.transcript,
            },
            analyzed={
                "summary": model.summary,
                "key_points": model.key_points,
                "action_items": model.action_items,
                "keywords": model.keywords,
            },
            metadata={
                "db_id": model.id,
                "user_id": model.user_id,
                "last_synced_at": model.last_synced_at.isoformat() if model.last_synced_at else None,
                "created_at": model.created_at.isoformat() if model.created_at else None,
                "updated_at": model.updated_at.isoformat() if model.updated_at else None,
            },
        )

    def from_indexed_entity(self, entity: IndexedEntity) -> dict[str, Any]:
        """Convert IndexedEntity to dict for MeetingNote creation/update."""
        structured = entity.structured
        analyzed = entity.analyzed
        metadata = entity.metadata

        result = {
            "fireflies_id": structured.get("fireflies_id"),
            "title": structured.get("title"),
            "duration_minutes": structured.get("duration_minutes"),
            "participants": structured.get("participants"),
            "transcript": structured.get("transcript"),
            "summary": analyzed.get("summary"),
            "key_points": analyzed.get("key_points"),
            "action_items": analyzed.get("action_items"),
            "keywords": analyzed.get("keywords"),
            "user_id": metadata.get("user_id"),
        }

        # Handle meeting_date
        if structured.get("meeting_date"):
            if isinstance(structured["meeting_date"], str):
                result["meeting_date"] = datetime.fromisoformat(structured["meeting_date"])
            else:
                result["meeting_date"] = structured["meeting_date"]

        return result

    async def get_by_id(self, session: AsyncSession, entity_id: str) -> MeetingNote | None:
        """Retrieve MeetingNote by entity ID."""
        fireflies_id = self.parse_entity_id(entity_id)
        result = await session.execute(
            select(MeetingNote).where(MeetingNote.fireflies_id == fireflies_id)
        )
        return result.scalar_one_or_none()

    async def store(self, session: AsyncSession, entity: IndexedEntity) -> str:
        """Store a meeting entity (upsert)."""
        data = self.from_indexed_entity(entity)
        fireflies_id = data.get("fireflies_id")

        if not fireflies_id:
            raise ValueError("Meeting must have a fireflies_id")

        # Check if exists
        existing = await session.execute(
            select(MeetingNote).where(MeetingNote.fireflies_id == fireflies_id)
        )
        model = existing.scalar_one_or_none()

        if model:
            # Update existing
            for key, value in data.items():
                if value is not None and key != "fireflies_id":
                    setattr(model, key, value)
            model.last_synced_at = datetime.utcnow()
        else:
            # Create new - require user_id
            if not data.get("user_id"):
                raise ValueError("Meeting must have a user_id")
            data["last_synced_at"] = datetime.utcnow()
            model = MeetingNote(**data)
            session.add(model)

        await session.flush()
        return entity.id

    async def delete(self, session: AsyncSession, entity_id: str) -> bool:
        """Delete a meeting by entity ID."""
        fireflies_id = self.parse_entity_id(entity_id)
        result = await session.execute(
            select(MeetingNote).where(MeetingNote.fireflies_id == fireflies_id)
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
    ) -> list[MeetingNote]:
        """Query meetings with filters."""
        query = select(MeetingNote)

        # Apply filters
        if "user_id" in filters:
            query = query.where(MeetingNote.user_id == filters["user_id"])
        if "title" in filters:
            query = query.where(MeetingNote.title.ilike(f"%{filters['title']}%"))
        if "meeting_after" in filters:
            query = query.where(MeetingNote.meeting_date >= filters["meeting_after"])
        if "meeting_before" in filters:
            query = query.where(MeetingNote.meeting_date <= filters["meeting_before"])
        if "participant" in filters:
            # Check if participant is in the array
            query = query.where(MeetingNote.participants.any(filters["participant"]))

        query = query.order_by(MeetingNote.meeting_date.desc()).limit(limit)

        result = await session.execute(query)
        return list(result.scalars().all())

    def get_embedding_text(self, entity: IndexedEntity) -> str:
        """Generate embedding text for meeting."""
        structured = entity.structured
        analyzed = entity.analyzed

        parts = []

        # Title
        if structured.get("title"):
            parts.append(f"Meeting: {structured['title']}")

        # Date
        if structured.get("meeting_date"):
            parts.append(f"Date: {structured['meeting_date']}")

        # Participants
        if structured.get("participants"):
            parts.append(f"Participants: {', '.join(structured['participants'])}")

        # Summary
        if analyzed.get("summary"):
            parts.append(f"Summary: {analyzed['summary']}")

        # Key points
        if analyzed.get("key_points"):
            points = analyzed["key_points"]
            if isinstance(points, list):
                parts.append(f"Key Points: {'; '.join(points)}")

        # Action items
        if analyzed.get("action_items"):
            items = analyzed["action_items"]
            if isinstance(items, list):
                parts.append(f"Action Items: {'; '.join(items)}")

        # Keywords
        if analyzed.get("keywords"):
            keywords = analyzed["keywords"]
            if isinstance(keywords, list):
                parts.append(f"Keywords: {', '.join(keywords)}")

        return "\n".join(parts)
