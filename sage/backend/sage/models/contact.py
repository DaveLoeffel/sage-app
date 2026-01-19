"""Contact model for relationship tracking."""

from datetime import datetime
from enum import Enum

from sqlalchemy import String, DateTime, Text, Integer, ForeignKey, Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column

from sage.services.database import Base


class ContactCategory(str, Enum):
    """Contact category for relationship management."""

    TEAM = "team"
    INVESTOR = "investor"
    VENDOR = "vendor"
    FAMILY = "family"
    CLIENT = "client"
    PARTNER = "partner"
    OTHER = "other"


class Contact(Base):
    """Contact model for tracking relationships and escalation chains."""

    __tablename__ = "contacts"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    company: Mapped[str | None] = mapped_column(String(255), nullable=True)
    role: Mapped[str | None] = mapped_column(String(255), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # Categorization
    category: Mapped[ContactCategory] = mapped_column(
        SQLEnum(ContactCategory), default=ContactCategory.OTHER
    )

    # Escalation chain (for follow-up escalation)
    reports_to_id: Mapped[int | None] = mapped_column(
        ForeignKey("contacts.id"), nullable=True
    )
    supervisor_email: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Response expectations
    expected_response_days: Mapped[int] = mapped_column(Integer, default=2)

    # Notes and context
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    ai_context: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Interaction tracking
    last_email_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_meeting_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    email_count: Mapped[int] = mapped_column(Integer, default=0)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )
