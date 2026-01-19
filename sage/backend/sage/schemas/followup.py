"""Follow-up schemas."""

from datetime import datetime

from pydantic import BaseModel, EmailStr

from sage.models.followup import FollowupStatus, FollowupPriority


class FollowupBase(BaseModel):
    """Base follow-up schema."""

    subject: str
    contact_email: EmailStr
    contact_name: str | None = None
    priority: FollowupPriority = FollowupPriority.NORMAL
    due_date: datetime
    notes: str | None = None
    escalation_email: EmailStr | None = None
    escalation_days: int = 7


class FollowupCreate(FollowupBase):
    """Schema for creating a follow-up."""

    gmail_id: str
    thread_id: str
    email_id: int | None = None


class FollowupUpdate(BaseModel):
    """Schema for updating a follow-up."""

    status: FollowupStatus | None = None
    priority: FollowupPriority | None = None
    due_date: datetime | None = None
    notes: str | None = None
    escalation_email: EmailStr | None = None
    escalation_days: int | None = None


class FollowupResponse(FollowupBase):
    """Schema for follow-up response."""

    id: int
    user_id: int
    gmail_id: str
    thread_id: str
    status: FollowupStatus
    ai_summary: str | None = None
    reminder_sent_at: datetime | None = None
    escalated_at: datetime | None = None
    completed_at: datetime | None = None
    completed_reason: str | None = None
    created_at: datetime
    updated_at: datetime

    # Computed fields
    is_overdue: bool = False
    days_until_due: int | None = None

    class Config:
        from_attributes = True


class FollowupListResponse(BaseModel):
    """Schema for paginated follow-up list."""

    followups: list[FollowupResponse]
    total: int
    pending_count: int
    overdue_count: int
