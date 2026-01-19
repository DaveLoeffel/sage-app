"""Email schemas."""

from datetime import datetime

from pydantic import BaseModel, EmailStr, computed_field

from sage.models.email import EmailCategory, EmailPriority


class EmailAnalysis(BaseModel):
    """AI analysis of an email."""

    category: EmailCategory
    priority: EmailPriority
    summary: str
    action_items: list[str] | None = None
    sentiment: str | None = None
    requires_response: bool
    suggested_response_time: str | None = None


class EmailResponse(BaseModel):
    """Schema for email response."""

    id: int
    gmail_id: str
    thread_id: str
    subject: str
    sender_email: str
    sender_name: str | None = None
    to_emails: list[str] | None = None
    snippet: str | None = None
    body_text: str | None = None
    labels: list[str] | None = None
    is_unread: bool
    has_attachments: bool
    received_at: datetime

    # AI analysis
    category: EmailCategory | None = None
    priority: EmailPriority | None = None
    summary: str | None = None
    requires_response: bool | None = None

    @computed_field
    @property
    def is_in_inbox(self) -> bool:
        """Check if email is still in inbox (not archived/filed)."""
        return self.labels is not None and "INBOX" in self.labels

    @computed_field
    @property
    def needs_attention(self) -> bool:
        """Check if email needs attention (unread AND in inbox)."""
        return self.is_unread and self.is_in_inbox

    class Config:
        from_attributes = True


class EmailListResponse(BaseModel):
    """Schema for paginated email list."""

    emails: list[EmailResponse]
    total: int
    page: int
    page_size: int
    has_next: bool


class DraftReplyRequest(BaseModel):
    """Schema for generating a draft reply."""

    tone: str | None = None  # e.g., "professional", "friendly", "brief"
    key_points: list[str] | None = None
    context: str | None = None


class DraftReplyResponse(BaseModel):
    """Schema for draft reply response."""

    subject: str
    body: str
    suggested_attachments: list[str] | None = None
    confidence: float
    notes: str | None = None
