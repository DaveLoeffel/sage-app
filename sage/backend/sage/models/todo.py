"""Todo item tracking model."""

from datetime import datetime, date
from enum import Enum
from typing import TYPE_CHECKING

from sqlalchemy import String, DateTime, Date, Text, Integer, ForeignKey, Enum as SQLEnum, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship

from sage.services.database import Base

if TYPE_CHECKING:
    from sage.models.user import User


class TodoCategory(str, Enum):
    """How the todo item was detected."""

    SELF_REMINDER = "self_reminder"  # Dave reminding himself (email to self, "Reminder:" prefix)
    REQUEST_RECEIVED = "request_received"  # Someone asks Dave to do something
    COMMITMENT_MADE = "commitment_made"  # Dave promises to do something in sent email
    MEETING_ACTION = "meeting_action"  # Action item from meeting transcript
    MANUAL = "manual"  # Manually created by user


class TodoPriority(str, Enum):
    """Todo priority level."""

    LOW = "low"  # Nice-to-have, "when you get a chance"
    NORMAL = "normal"  # Standard requests
    HIGH = "high"  # VIP sender, deadline within 1 week, financial/legal
    URGENT = "urgent"  # Explicit 24h deadline, ASAP, urgent


class TodoStatus(str, Enum):
    """Todo status."""

    PENDING = "pending"  # Not yet started
    SNOOZED = "snoozed"  # Postponed to later date
    COMPLETED = "completed"  # Done
    CANCELLED = "cancelled"  # No longer needed


class TodoItem(Base):
    """Track action items from emails and meetings."""

    __tablename__ = "todo_items"

    id: Mapped[int] = mapped_column(primary_key=True)

    # User relationship
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    user: Mapped["User"] = relationship(back_populates="todos")

    # Core todo info
    title: Mapped[str] = mapped_column(String(500))  # Brief description
    description: Mapped[str | None] = mapped_column(Text, nullable=True)  # Full context

    # Classification
    category: Mapped[TodoCategory] = mapped_column(
        SQLEnum(TodoCategory, values_callable=lambda x: [e.value for e in x]),
        index=True
    )
    priority: Mapped[TodoPriority] = mapped_column(
        SQLEnum(TodoPriority, values_callable=lambda x: [e.value for e in x]),
        default=TodoPriority.NORMAL,
        index=True
    )
    status: Mapped[TodoStatus] = mapped_column(
        SQLEnum(TodoStatus, values_callable=lambda x: [e.value for e in x]),
        default=TodoStatus.PENDING,
        index=True
    )

    # Timing
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    snoozed_until: Mapped[date | None] = mapped_column(Date, nullable=True)

    # Source tracking (where this todo came from)
    source_type: Mapped[str] = mapped_column(String(50))  # email, meeting, manual
    source_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)  # gmail_id or meeting_id
    source_summary: Mapped[str | None] = mapped_column(String(500), nullable=True)  # "Request from Laura Hodgson, Jan 18"

    # Contact info (who made the request, if applicable)
    contact_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    contact_email: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)

    # AI detection metadata
    detection_confidence: Mapped[float | None] = mapped_column(nullable=True)  # 0.0-1.0
    detected_deadline_text: Mapped[str | None] = mapped_column(String(255), nullable=True)  # Original text like "by Friday"

    # Action timestamps
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    completed_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    __table_args__ = (
        Index("ix_todo_status_due", "status", "due_date"),
        Index("ix_todo_user_status", "user_id", "status"),
        Index("ix_todo_user_priority", "user_id", "priority"),
        Index("ix_todo_source", "source_type", "source_id"),
    )

    def mark_completed(self, reason: str = "Completed") -> None:
        """Mark todo as completed."""
        self.status = TodoStatus.COMPLETED
        self.completed_at = datetime.utcnow()
        self.completed_reason = reason

    def mark_cancelled(self, reason: str = "Cancelled") -> None:
        """Mark todo as cancelled."""
        self.status = TodoStatus.CANCELLED
        self.completed_at = datetime.utcnow()
        self.completed_reason = reason

    def snooze(self, until: date) -> None:
        """Snooze todo until a later date."""
        self.status = TodoStatus.SNOOZED
        self.snoozed_until = until

    def unsnooze(self) -> None:
        """Restore snoozed todo to pending."""
        self.status = TodoStatus.PENDING
        self.snoozed_until = None
