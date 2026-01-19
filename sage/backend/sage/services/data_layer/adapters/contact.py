"""Contact adapter for converting between Contact and IndexedEntity."""

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from sage.agents.base import IndexedEntity
from sage.models.contact import Contact, ContactCategory
from sage.services.data_layer.adapters.base import BaseEntityAdapter


class ContactAdapter(BaseEntityAdapter[Contact]):
    """Adapter for contact entities stored in contacts table."""

    entity_type = "contact"

    def to_indexed_entity(self, model: Contact) -> IndexedEntity:
        """Convert Contact to IndexedEntity."""
        return IndexedEntity(
            id=self.make_entity_id(model.id),
            entity_type=self.entity_type,
            source="database",
            structured={
                "email": model.email,
                "name": model.name,
                "company": model.company,
                "role": model.role,
                "phone": model.phone,
                "category": model.category.value if model.category else None,
                "reports_to_id": model.reports_to_id,
                "supervisor_email": model.supervisor_email,
                "expected_response_days": model.expected_response_days,
            },
            analyzed={
                "notes": model.notes,
                "ai_context": model.ai_context,
            },
            metadata={
                "db_id": model.id,
                "last_email_at": model.last_email_at.isoformat() if model.last_email_at else None,
                "last_meeting_at": model.last_meeting_at.isoformat() if model.last_meeting_at else None,
                "email_count": model.email_count,
                "created_at": model.created_at.isoformat() if model.created_at else None,
                "updated_at": model.updated_at.isoformat() if model.updated_at else None,
            },
        )

    def from_indexed_entity(self, entity: IndexedEntity) -> dict[str, Any]:
        """Convert IndexedEntity to dict for Contact creation/update."""
        structured = entity.structured
        analyzed = entity.analyzed

        result = {
            "email": structured.get("email"),
            "name": structured.get("name"),
            "company": structured.get("company"),
            "role": structured.get("role"),
            "phone": structured.get("phone"),
            "reports_to_id": structured.get("reports_to_id"),
            "supervisor_email": structured.get("supervisor_email"),
            "expected_response_days": structured.get("expected_response_days", 2),
            "notes": analyzed.get("notes"),
            "ai_context": analyzed.get("ai_context"),
        }

        # Handle category enum
        if structured.get("category"):
            try:
                result["category"] = ContactCategory(structured["category"])
            except ValueError:
                result["category"] = ContactCategory.OTHER

        return result

    async def get_by_id(self, session: AsyncSession, entity_id: str) -> Contact | None:
        """Retrieve Contact by entity ID."""
        db_id = self.parse_entity_id(entity_id)
        try:
            db_id_int = int(db_id)
        except ValueError:
            return None

        result = await session.execute(
            select(Contact).where(Contact.id == db_id_int)
        )
        return result.scalar_one_or_none()

    async def get_by_email(self, session: AsyncSession, email: str) -> Contact | None:
        """Retrieve Contact by email address."""
        result = await session.execute(
            select(Contact).where(Contact.email == email)
        )
        return result.scalar_one_or_none()

    async def store(self, session: AsyncSession, entity: IndexedEntity) -> str:
        """Store a contact entity (upsert)."""
        data = self.from_indexed_entity(entity)
        email = data.get("email")

        if not email:
            raise ValueError("Contact must have an email address")

        # Check if exists by email
        existing = await session.execute(
            select(Contact).where(Contact.email == email)
        )
        model = existing.scalar_one_or_none()

        if model:
            # Update existing
            for key, value in data.items():
                if value is not None and key != "email":
                    setattr(model, key, value)
        else:
            # Create new
            model = Contact(**data)
            session.add(model)

        await session.flush()
        return self.make_entity_id(model.id)

    async def delete(self, session: AsyncSession, entity_id: str) -> bool:
        """Delete a contact by entity ID."""
        db_id = self.parse_entity_id(entity_id)
        try:
            db_id_int = int(db_id)
        except ValueError:
            return False

        result = await session.execute(
            select(Contact).where(Contact.id == db_id_int)
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
    ) -> list[Contact]:
        """Query contacts with filters."""
        query = select(Contact)

        # Apply filters
        if "email" in filters:
            query = query.where(Contact.email == filters["email"])
        if "name" in filters:
            query = query.where(Contact.name.ilike(f"%{filters['name']}%"))
        if "company" in filters:
            query = query.where(Contact.company.ilike(f"%{filters['company']}%"))
        if "category" in filters:
            if isinstance(filters["category"], str):
                try:
                    filters["category"] = ContactCategory(filters["category"])
                except ValueError:
                    pass
            query = query.where(Contact.category == filters["category"])

        query = query.order_by(Contact.updated_at.desc()).limit(limit)

        result = await session.execute(query)
        return list(result.scalars().all())

    def get_embedding_text(self, entity: IndexedEntity) -> str:
        """Generate embedding text for contact."""
        structured = entity.structured
        analyzed = entity.analyzed

        parts = []

        # Name and email
        if structured.get("name"):
            parts.append(f"Name: {structured['name']}")
        if structured.get("email"):
            parts.append(f"Email: {structured['email']}")

        # Company and role
        if structured.get("company"):
            parts.append(f"Company: {structured['company']}")
        if structured.get("role"):
            parts.append(f"Role: {structured['role']}")

        # Category
        if structured.get("category"):
            parts.append(f"Category: {structured['category']}")

        # Notes and AI context
        if analyzed.get("notes"):
            parts.append(f"Notes: {analyzed['notes']}")
        if analyzed.get("ai_context"):
            parts.append(f"Context: {analyzed['ai_context']}")

        return "\n".join(parts)
