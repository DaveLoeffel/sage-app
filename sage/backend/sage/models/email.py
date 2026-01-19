"""Email cache model."""

from datetime import datetime
from enum import Enum

from sqlalchemy import String, DateTime, Text, Integer, Enum as SQLEnum, Index
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import ARRAY

from sage.services.database import Base


class EmailCategory(str, Enum):
    """Email category for AI classification."""

    URGENT = "urgent"
    ACTION_REQUIRED = "action_required"
    FYI = "fyi"
    NEWSLETTER = "newsletter"
    PERSONAL = "personal"
    SPAM = "spam"
    UNKNOWN = "unknown"


class EmailPriority(str, Enum):
    """Email priority level."""

    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


class EmailCache(Base):
    """Cached email from Gmail for fast access and analysis."""

    __tablename__ = "email_cache"

    id: Mapped[int] = mapped_column(primary_key=True)

    # Gmail identifiers
    gmail_id: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    thread_id: Mapped[str] = mapped_column(String(255), index=True)
    history_id: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Email content
    subject: Mapped[str] = mapped_column(String(500))
    sender_email: Mapped[str] = mapped_column(String(255), index=True)
    sender_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    to_emails: Mapped[list[str] | None] = mapped_column(ARRAY(String(255)), nullable=True)
    cc_emails: Mapped[list[str] | None] = mapped_column(ARRAY(String(255)), nullable=True)
    body_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    body_html: Mapped[str | None] = mapped_column(Text, nullable=True)
    snippet: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Gmail metadata
    labels: Mapped[list[str] | None] = mapped_column(ARRAY(String(100)), nullable=True)
    is_unread: Mapped[bool] = mapped_column(default=True)
    has_attachments: Mapped[bool] = mapped_column(default=False)
    received_at: Mapped[datetime] = mapped_column(DateTime, index=True)

    # AI analysis results
    category: Mapped[EmailCategory | None] = mapped_column(
        SQLEnum(EmailCategory, values_callable=lambda x: [e.value for e in x]),
        nullable=True
    )
    priority: Mapped[EmailPriority | None] = mapped_column(
        SQLEnum(EmailPriority, values_callable=lambda x: [e.value for e in x]),
        nullable=True
    )
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    action_items: Mapped[str | None] = mapped_column(Text, nullable=True)
    sentiment: Mapped[str | None] = mapped_column(String(50), nullable=True)
    requires_response: Mapped[bool | None] = mapped_column(nullable=True)

    # Vector search reference
    qdrant_id: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Timestamps
    synced_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    analyzed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    __table_args__ = (
        Index("ix_email_cache_received_sender", "received_at", "sender_email"),
    )

    @property
    def is_in_inbox(self) -> bool:
        """Check if email is still in inbox (not archived/filed)."""
        return self.labels is not None and "INBOX" in self.labels

    @property
    def needs_attention(self) -> bool:
        """Check if email needs attention (unread AND in inbox)."""
        return self.is_unread and self.is_in_inbox
