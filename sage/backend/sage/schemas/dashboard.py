"""Dashboard schemas."""

from datetime import datetime

from pydantic import BaseModel

from sage.schemas.email import EmailResponse
from sage.schemas.followup import FollowupResponse


class CalendarEvent(BaseModel):
    """Schema for calendar event."""

    id: str
    title: str
    start: datetime
    end: datetime
    location: str | None = None
    attendees: list[str] | None = None
    description: str | None = None
    meeting_link: str | None = None


class StockQuote(BaseModel):
    """Schema for stock quote."""

    symbol: str
    price: float
    change: float
    change_percent: float
    last_updated: datetime


class FollowupSummary(BaseModel):
    """Summary of follow-up status."""

    total: int
    pending: int
    overdue: int
    reminded: int
    escalated: int
    completed_today: int


class EmailSummary(BaseModel):
    """Summary of email inbox."""

    unread_count: int
    urgent_count: int
    action_required_count: int
    last_sync: datetime | None = None


class DashboardSummary(BaseModel):
    """Complete dashboard summary."""

    # Follow-ups
    followup_summary: FollowupSummary
    overdue_followups: list[FollowupResponse]
    upcoming_followups: list[FollowupResponse]

    # Emails
    email_summary: EmailSummary
    priority_emails: list[EmailResponse]

    # Calendar
    todays_events: list[CalendarEvent]
    next_event: CalendarEvent | None = None

    # Optional widgets
    stock_quotes: list[StockQuote] | None = None

    # Metadata
    generated_at: datetime
    user_timezone: str
