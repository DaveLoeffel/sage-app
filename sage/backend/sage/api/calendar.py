"""Calendar API endpoints."""

from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from sage.api.auth import get_current_user
from sage.config import get_settings
from sage.services.database import get_db
from sage.models.user import User
from sage.schemas.dashboard import CalendarEvent

router = APIRouter()
settings = get_settings()


def get_google_calendar_service(user: User):
    """Create Google Calendar API service for a user."""
    if not user.google_access_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Google Calendar not connected. Please re-authenticate.",
        )

    credentials = Credentials(
        token=user.google_access_token,
        refresh_token=user.google_refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=settings.google_client_id,
        client_secret=settings.google_client_secret,
    )

    return build("calendar", "v3", credentials=credentials)


def parse_calendar_event(event: dict) -> CalendarEvent:
    """Parse a Google Calendar event into our schema."""
    # Handle all-day events vs timed events
    start = event.get("start", {})
    end = event.get("end", {})

    if "dateTime" in start:
        start_dt = datetime.fromisoformat(start["dateTime"].replace("Z", "+00:00"))
    else:
        # All-day event
        start_dt = datetime.fromisoformat(start.get("date", "")).replace(
            hour=0, minute=0, second=0, tzinfo=timezone.utc
        )

    if "dateTime" in end:
        end_dt = datetime.fromisoformat(end["dateTime"].replace("Z", "+00:00"))
    else:
        # All-day event
        end_dt = datetime.fromisoformat(end.get("date", "")).replace(
            hour=23, minute=59, second=59, tzinfo=timezone.utc
        )

    # Extract attendees
    attendees = []
    for attendee in event.get("attendees", []):
        email = attendee.get("email", "")
        name = attendee.get("displayName", email)
        attendees.append(name if name else email)

    # Extract meeting link from conferenceData
    meeting_link = None
    conference_data = event.get("conferenceData", {})
    entry_points = conference_data.get("entryPoints", [])
    for entry in entry_points:
        if entry.get("entryPointType") == "video":
            meeting_link = entry.get("uri")
            break

    # Also check hangoutLink
    if not meeting_link:
        meeting_link = event.get("hangoutLink")

    return CalendarEvent(
        id=event.get("id", ""),
        title=event.get("summary", "No Title"),
        start=start_dt,
        end=end_dt,
        location=event.get("location"),
        attendees=attendees if attendees else None,
        description=event.get("description"),
        meeting_link=meeting_link,
    )


@router.get("/events", response_model=list[CalendarEvent])
async def list_events(
    user: Annotated[User, Depends(get_current_user)],
    start_date: datetime | None = None,
    end_date: datetime | None = None,
    max_results: int = Query(10, ge=1, le=100),
) -> list[CalendarEvent]:
    """List calendar events within a date range."""
    # Default to today and next 7 days
    if not start_date:
        start_date = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    if not end_date:
        end_date = start_date + timedelta(days=7)

    try:
        service = get_google_calendar_service(user)

        # Convert to RFC3339 format
        time_min = start_date.isoformat()
        time_max = end_date.isoformat()

        events_result = (
            service.events()
            .list(
                calendarId="primary",
                timeMin=time_min,
                timeMax=time_max,
                maxResults=max_results,
                singleEvents=True,
                orderBy="startTime",
            )
            .execute()
        )

        events = events_result.get("items", [])
        return [parse_calendar_event(event) for event in events]

    except HttpError as e:
        if e.resp.status == 401:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Google Calendar authorization expired. Please re-authenticate.",
            )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to fetch calendar events: {str(e)}",
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to fetch calendar events: {str(e)}",
        )


@router.get("/today", response_model=list[CalendarEvent])
async def get_todays_events(
    user: Annotated[User, Depends(get_current_user)],
) -> list[CalendarEvent]:
    """Get today's calendar events."""
    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    today_end = today_start + timedelta(days=1)

    try:
        service = get_google_calendar_service(user)

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
        return [parse_calendar_event(event) for event in events]

    except HttpError as e:
        if e.resp.status == 401:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Google Calendar authorization expired. Please re-authenticate.",
            )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to fetch today's events: {str(e)}",
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to fetch today's events: {str(e)}",
        )


@router.get("/next", response_model=CalendarEvent | None)
async def get_next_event(
    user: Annotated[User, Depends(get_current_user)],
) -> CalendarEvent | None:
    """Get the next upcoming calendar event."""
    now = datetime.now(timezone.utc)

    try:
        service = get_google_calendar_service(user)

        events_result = (
            service.events()
            .list(
                calendarId="primary",
                timeMin=now.isoformat(),
                maxResults=1,
                singleEvents=True,
                orderBy="startTime",
            )
            .execute()
        )

        events = events_result.get("items", [])
        if events:
            return parse_calendar_event(events[0])
        return None

    except HttpError as e:
        if e.resp.status == 401:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Google Calendar authorization expired. Please re-authenticate.",
            )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to fetch next event: {str(e)}",
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to fetch next event: {str(e)}",
        )


@router.get("/event/{event_id}/context")
async def get_event_context(
    event_id: str,
    user: Annotated[User, Depends(get_current_user)],
) -> dict:
    """Get AI-generated context for a calendar event (meeting prep)."""
    # TODO: Implement meeting prep using Claude Agent
    # - Get last 10 emails with attendees
    # - Get previous meeting notes from Fireflies
    # - Get open loops/followups with attendees
    return {
        "event_id": event_id,
        "recent_emails": [],
        "previous_meetings": [],
        "open_loops": [],
        "suggested_topics": [],
    }
