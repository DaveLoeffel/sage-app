"""Dashboard API endpoints."""

from datetime import datetime, timedelta, timezone
from typing import Annotated
import logging

from fastapi import APIRouter, Depends
from sqlalchemy import select, func, and_, text
from sqlalchemy.ext.asyncio import AsyncSession
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from sage.services.database import get_db
from sage.api.auth import get_current_user
from sage.models.email import EmailCache, EmailCategory, EmailPriority
from sage.models.followup import Followup, FollowupStatus
from sage.models.todo import TodoItem, TodoStatus
from sage.models.user import User
from sage.schemas.dashboard import (
    DashboardSummary,
    FollowupSummary,
    EmailSummary,
    TodoSummary,
    CalendarEvent,
    StockQuote,
)
from sage.schemas.email import EmailResponse
from sage.schemas.followup import FollowupResponse
from sage.config import get_settings

router = APIRouter()
settings = get_settings()
logger = logging.getLogger(__name__)


def get_todays_calendar_events(user: User) -> list[CalendarEvent]:
    """Fetch today's calendar events from Google Calendar."""
    if not user.google_access_token:
        logger.warning("No Google access token for user, skipping calendar fetch")
        return []

    try:
        credentials = Credentials(
            token=user.google_access_token,
            refresh_token=user.google_refresh_token,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=settings.google_client_id,
            client_secret=settings.google_client_secret,
        )

        service = build("calendar", "v3", credentials=credentials)

        # Get today's events
        now = datetime.now(timezone.utc)
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        today_end = today_start + timedelta(days=1)

        events_result = (
            service.events()
            .list(
                calendarId="primary",
                timeMin=today_start.isoformat(),
                timeMax=today_end.isoformat(),
                maxResults=50,
                singleEvents=True,
                orderBy="startTime",
            )
            .execute()
        )

        events = events_result.get("items", [])
        calendar_events = []

        for event in events:
            # Handle all-day events vs timed events
            start = event.get("start", {})
            end = event.get("end", {})

            if "dateTime" in start:
                start_dt = datetime.fromisoformat(start["dateTime"].replace("Z", "+00:00"))
            else:
                start_dt = datetime.fromisoformat(start.get("date", "")).replace(
                    hour=0, minute=0, second=0, tzinfo=timezone.utc
                )

            if "dateTime" in end:
                end_dt = datetime.fromisoformat(end["dateTime"].replace("Z", "+00:00"))
            else:
                end_dt = datetime.fromisoformat(end.get("date", "")).replace(
                    hour=23, minute=59, second=59, tzinfo=timezone.utc
                )

            # Extract attendees
            attendees = []
            for attendee in event.get("attendees", []):
                email = attendee.get("email", "")
                name = attendee.get("displayName", email)
                attendees.append(name if name else email)

            # Extract meeting link
            meeting_link = None
            conference_data = event.get("conferenceData", {})
            entry_points = conference_data.get("entryPoints", [])
            for entry in entry_points:
                if entry.get("entryPointType") == "video":
                    meeting_link = entry.get("uri")
                    break
            if not meeting_link:
                meeting_link = event.get("hangoutLink")

            calendar_events.append(CalendarEvent(
                id=event.get("id", ""),
                title=event.get("summary", "No Title"),
                start=start_dt,
                end=end_dt,
                location=event.get("location"),
                attendees=attendees if attendees else None,
                description=event.get("description"),
                meeting_link=meeting_link,
            ))

        return calendar_events

    except HttpError as e:
        logger.error(f"Google Calendar API error: {e}")
        return []
    except Exception as e:
        logger.error(f"Error fetching calendar events: {e}")
        return []


@router.get("/summary", response_model=DashboardSummary)
async def get_dashboard_summary(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
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
    # Use PostgreSQL array contains operator (@>) to check if "INBOX" is in labels
    # Cast to varchar[] to match the labels column type
    inbox_filter = text("labels @> ARRAY['INBOX']::varchar[]")

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

    # Get todo stats
    from datetime import date
    today = date.today()
    week_end = today + timedelta(days=7)

    # Count pending todos
    pending_todos_result = await db.execute(
        select(TodoItem).where(TodoItem.status == TodoStatus.PENDING)
    )
    pending_todos = pending_todos_result.scalars().all()

    todo_overdue = sum(1 for t in pending_todos if t.due_date and t.due_date < today)
    todo_due_today = sum(1 for t in pending_todos if t.due_date == today)
    todo_due_this_week = sum(
        1 for t in pending_todos
        if t.due_date and t.due_date > today and t.due_date <= week_end
    )

    # Completed todos today
    todo_completed_today_result = await db.execute(
        select(func.count()).select_from(TodoItem).where(
            and_(
                TodoItem.status == TodoStatus.COMPLETED,
                TodoItem.completed_at >= today_start,
            )
        )
    )
    todo_completed_today = todo_completed_today_result.scalar() or 0

    todo_summary = TodoSummary(
        total_pending=len(pending_todos),
        overdue=todo_overdue,
        due_today=todo_due_today,
        due_this_week=todo_due_this_week,
        completed_today=todo_completed_today,
    )

    # Get today's calendar events from Google Calendar
    todays_events: list[CalendarEvent] = get_todays_calendar_events(user)

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
        todo_summary=todo_summary,
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
