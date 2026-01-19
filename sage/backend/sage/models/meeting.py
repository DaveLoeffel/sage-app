"""Meeting notes model for caching Fireflies data."""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import String, DateTime, Text, Integer, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import ARRAY, JSONB

from sage.services.database import Base

if TYPE_CHECKING:
    from sage.models.user import User


class MeetingNote(Base):
    """Cached meeting transcript and notes from Fireflies."""

    __tablename__ = "meeting_notes"

    id: Mapped[int] = mapped_column(primary_key=True)

    # User relationship
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    user: Mapped["User"] = relationship(back_populates="meeting_notes")

    # Fireflies identifiers
    fireflies_id: Mapped[str] = mapped_column(String(255), unique=True, index=True)

    # Meeting metadata
    title: Mapped[str] = mapped_column(String(500))
    meeting_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)
    duration_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Participants
    participants: Mapped[list[str] | None] = mapped_column(ARRAY(String), nullable=True)

    # Summary and content
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    key_points: Mapped[list[str] | None] = mapped_column(ARRAY(String), nullable=True)
    action_items: Mapped[list[str] | None] = mapped_column(ARRAY(String), nullable=True)
    keywords: Mapped[list[str] | None] = mapped_column(ARRAY(String), nullable=True)

    # Full transcript stored as JSON array of {speaker, text, timestamp}
    transcript: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # Cache management
    last_synced_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    __table_args__ = (
        Index("ix_meeting_notes_user_date", "user_id", "meeting_date"),
    )
