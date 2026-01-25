"""User model."""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import String, DateTime, Text, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship

from sage.services.database import Base

if TYPE_CHECKING:
    from sage.models.followup import Followup
    from sage.models.meeting import MeetingNote
    from sage.models.todo import TodoItem


class User(Base):
    """User model for OAuth authentication."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255))
    picture: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Google OAuth tokens
    google_access_token: Mapped[str | None] = mapped_column(Text, nullable=True)
    google_refresh_token: Mapped[str | None] = mapped_column(Text, nullable=True)
    google_token_expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # User settings
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    timezone: Mapped[str] = mapped_column(String(50), default="America/New_York")

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # Relationships
    followups: Mapped[list["Followup"]] = relationship(back_populates="user")
    meeting_notes: Mapped[list["MeetingNote"]] = relationship(back_populates="user")
    todos: Mapped[list["TodoItem"]] = relationship(back_populates="user")
