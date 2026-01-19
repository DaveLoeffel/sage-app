"""Dashboard API endpoints."""

from datetime import datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from sage.services.database import get_db
from sage.models.email import EmailCache, EmailCategory, EmailPriority
from sage.models.followup import Followup, FollowupStatus
from sage.schemas.dashboard import (
    DashboardSummary,
    FollowupSummary,
    EmailSummary,
    CalendarEvent,
    StockQuote,
)
from sage.schemas.email import EmailResponse
from sage.schemas.followup import FollowupResponse
from sage.config import get_settings

router = APIRouter()
settings = get_settings()


@router.get("/summary", response_model=DashboardSummary)
async def get_dashboard_summary(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> DashboardSummary:
    """Get complete dashboard summary."""
    now = datetime.utcnow()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    # Get follow-up stats
    followup_result = await db.execute(
        select(Followup).where(
            Followup.status.in_([
                FollowupStatus.PENDING,
                FollowupStatus.REMINDED,
                FollowupStatus.ESCALATED,
            ])
        )
    )
    active_followups = followup_result.scalars().all()

    pending_count = sum(1 for f in active_followups if f.status == FollowupStatus.PENDING)
    reminded_count = sum(1 for f in active_followups if f.status == FollowupStatus.REMINDED)
    escalated_count = sum(1 for f in active_followups if f.status == FollowupStatus.ESCALATED)
    overdue_count = sum(
        1 for f in active_followups
        if f.status in [FollowupStatus.PENDING, FollowupStatus.REMINDED]
        and f.due_date < now
    )

    # Get completed today count
    completed_today_result = await db.execute(
        select(func.count()).select_from(Followup).where(
            and_(
                Followup.status == FollowupStatus.COMPLETED,
                Followup.completed_at >= today_start,
            )
        )
    )
    completed_today = completed_today_result.scalar() or 0

    followup_summary = FollowupSummary(
        total=len(active_followups),
        pending=pending_count,
        overdue=overdue_count,
        reminded=reminded_count,
        escalated=escalated_count,
        completed_today=completed_today,
    )

    # Get overdue followups
    overdue_followups = [
        f for f in active_followups
        if f.status in [FollowupStatus.PENDING, FollowupStatus.REMINDED]
        and f.due_date < now
    ]
    overdue_followups.sort(key=lambda f: f.due_date)

    # Get upcoming followups (due in next 3 days)
    three_days = now + timedelta(days=3)
    upcoming_followups = [
        f for f in active_followups
        if f.due_date >= now and f.due_date <= three_days
    ]
    upcoming_followups.sort(key=lambda f: f.due_date)

    # Get email stats - only count emails that are in inbox (not archived/filed)
    # Emails filed out of inbox are no longer considered needing attention
    inbox_filter = EmailCache.labels.any("INBOX")

    unread_result = await db.execute(
        select(func.count()).select_from(EmailCache).where(
            and_(EmailCache.is_unread == True, inbox_filter)
        )
    )
    unread_count = unread_result.scalar() or 0

    urgent_result = await db.execute(
        select(func.count()).select_from(EmailCache).where(
            and_(
                EmailCache.is_unread == True,
                inbox_filter,
                EmailCache.priority == EmailPriority.URGENT,
            )
        )
    )
    urgent_count = urgent_result.scalar() or 0

    action_result = await db.execute(
        select(func.count()).select_from(EmailCache).where(
            and_(
                EmailCache.is_unread == True,
                inbox_filter,
                EmailCache.category == EmailCategory.ACTION_REQUIRED,
            )
        )
    )
    action_count = action_result.scalar() or 0

    # Get last sync time
    last_sync_result = await db.execute(
        select(func.max(EmailCache.synced_at))
    )
    last_sync = last_sync_result.scalar()

    email_summary = EmailSummary(
        unread_count=unread_count,
        urgent_count=urgent_count,
        action_required_count=action_count,
        last_sync=last_sync,
    )

    # Get priority emails (urgent or action required) - only from inbox
    priority_emails_result = await db.execute(
        select(EmailCache).where(
            and_(
                EmailCache.is_unread == True,
                inbox_filter,
                (EmailCache.priority == EmailPriority.URGENT)
                | (EmailCache.category == EmailCategory.ACTION_REQUIRED),
            )
        ).order_by(EmailCache.received_at.desc()).limit(5)
    )
    priority_emails = priority_emails_result.scalars().all()

    # TODO: Get calendar events from Google Calendar MCP
    todays_events: list[CalendarEvent] = []

    # TODO: Get stock quotes from Alpha Vantage MCP
    stock_quotes: list[StockQuote] | None = None

    return DashboardSummary(
        followup_summary=followup_summary,
        overdue_followups=[
            FollowupResponse.model_validate(f) for f in overdue_followups[:5]
        ],
        upcoming_followups=[
            FollowupResponse.model_validate(f) for f in upcoming_followups[:5]
        ],
        email_summary=email_summary,
        priority_emails=[
            EmailResponse.model_validate(e) for e in priority_emails
        ],
        todays_events=todays_events,
        next_event=todays_events[0] if todays_events else None,
        stock_quotes=stock_quotes,
        generated_at=now,
        user_timezone=settings.timezone,
    )


@router.get("/stats")
async def get_stats(
    db: Annotated[AsyncSession, Depends(get_db)],
    days: int = 7,
) -> dict:
    """Get statistics for the last N days."""
    now = datetime.utcnow()
    start_date = now - timedelta(days=days)

    # Email stats
    emails_received = await db.execute(
        select(func.count()).select_from(EmailCache).where(
            EmailCache.received_at >= start_date
        )
    )

    # Followup stats
    followups_created = await db.execute(
        select(func.count()).select_from(Followup).where(
            Followup.created_at >= start_date
        )
    )

    followups_completed = await db.execute(
        select(func.count()).select_from(Followup).where(
            and_(
                Followup.status == FollowupStatus.COMPLETED,
                Followup.completed_at >= start_date,
            )
        )
    )

    return {
        "period_days": days,
        "emails_received": emails_received.scalar() or 0,
        "followups_created": followups_created.scalar() or 0,
        "followups_completed": followups_completed.scalar() or 0,
    }


@router.get("/scheduler")
async def get_scheduler_status() -> dict:
    """Get status of scheduled jobs."""
    from sage.scheduler.jobs import get_job_status

    jobs = get_job_status()
    return {
        "jobs": jobs,
        "count": len(jobs),
    }
