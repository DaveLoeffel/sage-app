"""Briefing schemas."""

from datetime import datetime

from pydantic import BaseModel


class MorningBriefing(BaseModel):
    """Schema for morning briefing."""

    greeting: str
    date: str
    weather: str | None = None

    # Email summary
    overnight_emails_count: int
    urgent_emails: list[dict]
    action_required_emails: list[dict]

    # Follow-ups
    overdue_followups: list[dict]
    due_today_followups: list[dict]

    # Calendar
    todays_events: list[dict]
    next_meeting_in: str | None = None

    # Optional widgets
    stock_summary: str | None = None
    property_metrics: dict | None = None

    # AI insights
    key_priorities: list[str]
    suggested_actions: list[str]

    generated_at: datetime


class WeeklyReview(BaseModel):
    """Schema for weekly review briefing."""

    week_of: str

    # Email stats
    emails_received: int
    emails_sent: int
    avg_response_time: str | None = None

    # Follow-up stats
    followups_created: int
    followups_completed: int
    followups_escalated: int
    current_overdue: int

    # Meeting stats
    meetings_attended: int
    total_meeting_hours: float

    # AI insights
    key_accomplishments: list[str]
    areas_of_concern: list[str]
    recommendations: list[str]

    generated_at: datetime
