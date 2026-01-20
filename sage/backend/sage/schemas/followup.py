"""Follow-up schemas."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr

from sage.models.followup import FollowupStatus, FollowupPriority


class SourceEmailSummary(BaseModel):
    """Summary of source email for detail views."""

    id: int
    gmail_id: str
    subject: str
    sender_email: str
    sender_name: Optional[str] = None
    received_at: datetime
    snippet: Optional[str] = None
    body_text: Optional[str] = None


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
    email_id: Optional[int] = None
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

    # Source email summary (populated on detail view)
    source_email: Optional[SourceEmailSummary] = None

    class Config:
        from_attributes = True


class FollowupListResponse(BaseModel):
    """Schema for paginated follow-up list."""

    followups: list[FollowupResponse]
    total: int
    pending_count: int
    overdue_count: int


# Detection schemas

class FollowupDetectionProgress(BaseModel):
    """Progress tracking for followup detection."""

    status: str  # "running", "completed", "failed"
    phase: str
    percent_complete: int
    threads_analyzed: int = 0
    waiting_threads_found: int = 0
    followups_created: int = 0
    message: str | None = None
    error: str | None = None


class WaitingThreadResponse(BaseModel):
    """A thread waiting for response."""

    thread_id: str
    last_sent_at: datetime
    subject: str
    recipient_email: str
    recipient_name: str | None = None
    business_days_waiting: int
    suggested_action: str
    classification_method: str
    classification_confidence: float
    contact_phone: str | None = None


class FollowupDetectionResult(BaseModel):
    """Results from followup detection."""

    user_email: str
    detection_timestamp: datetime
    threads_analyzed: int
    waiting_threads: list[WaitingThreadResponse]
    heuristic_classifications: int
    ai_classifications: int


class DailyReviewItem(BaseModel):
    """Follow-up item for daily review with contact info."""

    id: int
    subject: str
    contact_email: str
    contact_name: str | None = None
    contact_phone: str | None = None
    status: str
    priority: str
    due_date: datetime
    days_overdue: int
    suggested_action: str
    notes: str | None = None
