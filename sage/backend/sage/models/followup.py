"""Follow-up tracking model."""

from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING

from sqlalchemy import String, DateTime, Text, Integer, ForeignKey, Enum as SQLEnum, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship

from sage.services.database import Base

if TYPE_CHECKING:
    from sage.models.user import User


class FollowupStatus(str, Enum):
    """Follow-up status state machine."""

    PENDING = "pending"  # Initial state, waiting for response
    REMINDED = "reminded"  # Day 2 reminder sent
    ESCALATED = "escalated"  # Day 7 escalation sent
    COMPLETED = "completed"  # Response received or manually closed
    CANCELLED = "cancelled"  # No longer needed


class FollowupPriority(str, Enum):
    """Follow-up priority level."""

    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


class Followup(Base):
    """Track emails requiring follow-up responses."""

    __tablename__ = "followups"

    id: Mapped[int] = mapped_column(primary_key=True)

    # User relationship
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    user: Mapped["User"] = relationship(back_populates="followups")

    # Email reference (nullable for meeting-based followups)
    email_id: Mapped[int | None] = mapped_column(
        ForeignKey("email_cache.id"), nullable=True
    )
    gmail_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    thread_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    subject: Mapped[str] = mapped_column(String(500))

    # Source tracking (where the followup came from)
    source_type: Mapped[str] = mapped_column(String(50), default="email")  # email, meeting
    source_id: Mapped[str | None] = mapped_column(String(255), nullable=True)  # meeting_id if from meeting

    # Contact info
    contact_email: Mapped[str] = mapped_column(String(255), index=True)
    contact_name: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Follow-up tracking
    status: Mapped[FollowupStatus] = mapped_column(
        SQLEnum(FollowupStatus, values_callable=lambda x: [e.value for e in x]),
        default=FollowupStatus.PENDING,
        index=True
    )
    priority: Mapped[FollowupPriority] = mapped_column(
        SQLEnum(FollowupPriority, values_callable=lambda x: [e.value for e in x]),
        default=FollowupPriority.NORMAL
    )
    due_date: Mapped[datetime] = mapped_column(DateTime, index=True)

    # Notes and context
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    ai_summary: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Escalation settings
    escalation_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    escalation_days: Mapped[int] = mapped_column(Integer, default=7)

    # Action timestamps
    reminder_sent_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    escalated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    completed_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    __table_args__ = (
        Index("ix_followups_status_due", "status", "due_date"),
        Index("ix_followups_user_status", "user_id", "status"),
    )

    def mark_reminded(self) -> None:
        """Mark follow-up as reminded."""
        self.status = FollowupStatus.REMINDED
        self.reminder_sent_at = datetime.utcnow()

    def mark_escalated(self) -> None:
        """Mark follow-up as escalated."""
        self.status = FollowupStatus.ESCALATED
        self.escalated_at = datetime.utcnow()

    def mark_completed(self, reason: str = "Response received") -> None:
        """Mark follow-up as completed."""
        self.status = FollowupStatus.COMPLETED
        self.completed_at = datetime.utcnow()
        self.completed_reason = reason

    def mark_cancelled(self, reason: str = "Cancelled by user") -> None:
        """Mark follow-up as cancelled."""
        self.status = FollowupStatus.CANCELLED
        self.completed_at = datetime.utcnow()
        self.completed_reason = reason
