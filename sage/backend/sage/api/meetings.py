"""Meeting notes API endpoints."""

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, or_, and_
from sqlalchemy.ext.asyncio import AsyncSession

from sage.api.auth import get_current_user
from sage.models.user import User
from sage.models.meeting import MeetingNote
from sage.models.email import EmailCache
from sage.schemas.meeting import (
    MeetingListItem,
    MeetingDetail,
    MeetingSummary,
    MeetingNoteResponse,
    MeetingSyncResponse,
    PlaudRecordingListItem,
    PlaudRecordingDetail,
    UnifiedMeetingItem,
    UnifiedSyncResponse,
)
from sage.services.database import get_db
from sage.services.fireflies import get_fireflies_service

router = APIRouter()

PLAUD_SUBJECT_PATTERN = "Meeting Notes from Plaud"
# Gmail label for Plaud recordings (user-defined label)
PLAUD_GMAIL_LABEL = "Plaud"
# Additional meeting notes from dloeffel@highlandsresidential.com sent before 2026-01-16
LEGACY_MEETING_NOTES_SENDER = "dloeffel@highlandsresidential.com"
LEGACY_MEETING_NOTES_PREFIX = "Meeting Notes"  # Case sensitive
LEGACY_MEETING_NOTES_CUTOFF = datetime(2026, 1, 16)  # Timezone-naive to match DB


@router.get("/status")
async def get_fireflies_status(
    user: Annotated[User, Depends(get_current_user)],
) -> dict:
    """Check if Fireflies integration is configured."""
    service = get_fireflies_service()
    return {
        "configured": service.is_configured,
        "message": "Fireflies API key is configured" if service.is_configured else "Fireflies API key not configured",
    }


@router.get("/recent", response_model=list[MeetingListItem])
async def list_recent_meetings(
    user: Annotated[User, Depends(get_current_user)],
    limit: int = Query(default=10, le=50),
) -> list[MeetingListItem]:
    """List recent meetings from Fireflies."""
    service = get_fireflies_service()

    if not service.is_configured:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Fireflies integration not configured",
        )

    try:
        meetings = await service.list_recent_meetings(limit=limit)
        return [MeetingListItem(**m) for m in meetings]
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to fetch meetings from Fireflies: {str(e)}",
        )


@router.get("/search", response_model=list[MeetingListItem])
async def search_meetings(
    user: Annotated[User, Depends(get_current_user)],
    query: str = Query(default=""),
    participant_email: str | None = Query(default=None),
    start_date: str | None = Query(default=None),
    end_date: str | None = Query(default=None),
    limit: int = Query(default=10, le=50),
) -> list[MeetingListItem]:
    """Search meetings by keyword or participant."""
    service = get_fireflies_service()

    if not service.is_configured:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Fireflies integration not configured",
        )

    try:
        meetings = await service.search_meetings(
            search_query=query,
            participant_email=participant_email,
            start_date=start_date,
            end_date=end_date,
            limit=limit,
        )
        return [MeetingListItem(**m) for m in meetings]
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to search meetings: {str(e)}",
        )


@router.post("/sync", response_model=MeetingSyncResponse)
async def sync_meetings(
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    limit: int = Query(default=20, le=50),
) -> MeetingSyncResponse:
    """Sync recent meetings from Fireflies to local cache."""
    service = get_fireflies_service()

    if not service.is_configured:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Fireflies integration not configured",
        )

    try:
        meetings = await service.list_recent_meetings(limit=limit)

        new_count = 0
        updated_count = 0

        for meeting_data in meetings:
            fireflies_id = meeting_data["id"]

            # Check if meeting already exists
            result = await db.execute(
                select(MeetingNote).where(MeetingNote.fireflies_id == fireflies_id)
            )
            existing = result.scalar_one_or_none()

            # Parse date
            meeting_date = None
            if meeting_data.get("date"):
                try:
                    parsed_date = datetime.fromisoformat(
                        meeting_data["date"].replace("Z", "+00:00")
                    )
                    # Convert to naive UTC for database storage
                    meeting_date = parsed_date.replace(tzinfo=None)
                except ValueError:
                    pass

            if existing:
                # Update existing record
                existing.title = meeting_data["title"]
                existing.meeting_date = meeting_date
                existing.duration_minutes = meeting_data.get("duration_minutes")
                existing.participants = meeting_data.get("participants")
                existing.last_synced_at = datetime.utcnow()
                updated_count += 1
            else:
                # Create new record
                meeting_note = MeetingNote(
                    user_id=user.id,
                    fireflies_id=fireflies_id,
                    title=meeting_data["title"],
                    meeting_date=meeting_date,
                    duration_minutes=meeting_data.get("duration_minutes"),
                    participants=meeting_data.get("participants"),
                    last_synced_at=datetime.utcnow(),
                )
                db.add(meeting_note)
                new_count += 1

        await db.commit()

        return MeetingSyncResponse(
            synced_count=len(meetings),
            new_count=new_count,
            updated_count=updated_count,
        )
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to sync meetings: {str(e)}",
        )


@router.get("/cached/list", response_model=list[MeetingNoteResponse])
async def list_cached_meetings(
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    limit: int = Query(default=20, le=100),
    offset: int = Query(default=0),
) -> list[MeetingNoteResponse]:
    """List cached meeting notes from local database."""
    result = await db.execute(
        select(MeetingNote)
        .where(MeetingNote.user_id == user.id)
        .order_by(MeetingNote.meeting_date.desc())
        .limit(limit)
        .offset(offset)
    )
    meetings = result.scalars().all()
    return [MeetingNoteResponse.model_validate(m) for m in meetings]


async def _get_plaud_label_id(db: AsyncSession) -> str | None:
    """Get the Gmail label ID for the 'Plaud' label."""
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build
    from sage.config import get_settings

    settings = get_settings()

    # Get user with Google credentials
    result = await db.execute(select(User).limit(1))
    user = result.scalar_one_or_none()

    if not user or not user.google_access_token:
        return None

    try:
        credentials = Credentials(
            token=user.google_access_token,
            refresh_token=user.google_refresh_token,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=settings.google_client_id,
            client_secret=settings.google_client_secret,
        )
        service = build("gmail", "v1", credentials=credentials)

        # List all labels and find the one named "Plaud"
        results = service.users().labels().list(userId="me").execute()
        labels = results.get("labels", [])

        for label in labels:
            if label.get("name") == PLAUD_GMAIL_LABEL:
                return label.get("id")

        return None
    except Exception:
        return None


@router.get("/plaud/label-id")
async def get_plaud_label_id(
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """Get the Gmail label ID for the 'Plaud' label."""
    label_id = await _get_plaud_label_id(db)
    return {
        "label_name": PLAUD_GMAIL_LABEL,
        "label_id": label_id,
        "found": label_id is not None,
    }


@router.post("/plaud/sync")
async def sync_plaud_recordings(
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    max_results: int = Query(default=100, le=500),
) -> dict:
    """Sync Plaud recordings from Gmail All Mail.

    Searches for emails with the 'Plaud' Gmail label.
    """
    from sage.core.email_processor import EmailProcessor

    # Use Gmail search by label name
    query = f"label:{PLAUD_GMAIL_LABEL}"

    processor = EmailProcessor(db)
    synced_count = await processor.sync_emails_by_query(query=query, max_results=max_results)

    # Get the label ID for reference
    label_id = await _get_plaud_label_id(db)

    return {
        "message": f"Synced {synced_count} Plaud recordings",
        "count": synced_count,
        "query": query,
        "label_id": label_id,
    }


@router.post("/plaud/sync-legacy")
async def sync_legacy_meeting_notes(
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    max_results: int = Query(default=100, le=500),
) -> dict:
    """Sync legacy meeting notes from Gmail All Mail.

    Searches for emails from dloeffel@highlandsresidential.com with subjects
    starting with 'Meeting Notes' sent before 2026-01-16.
    """
    from sage.core.email_processor import EmailProcessor

    # Gmail search query: from sender, subject starts with "Meeting Notes", before cutoff date
    # Gmail search is case-insensitive for subject, but our DB filter will apply case sensitivity
    query = f'from:{LEGACY_MEETING_NOTES_SENDER} subject:"Meeting Notes" before:2026/01/16'

    processor = EmailProcessor(db)
    synced_count = await processor.sync_emails_by_query(query=query, max_results=max_results)

    return {
        "message": f"Synced {synced_count} legacy meeting notes",
        "count": synced_count,
        "query": query,
    }


# ============== Plaud Recordings ==============
# NOTE: These routes MUST come before /{meeting_id} to avoid route conflicts


def _is_plaud_or_legacy_meeting_note(plaud_label_id: str | None = None):
    """Build filter for Plaud recordings and legacy meeting notes.

    Args:
        plaud_label_id: Gmail label ID for the 'Plaud' label. If provided,
                       emails with this label will also be included.
    """
    conditions = [
        # Original Plaud recordings by subject (case insensitive)
        EmailCache.subject.ilike(f"%{PLAUD_SUBJECT_PATTERN}%"),
        # Legacy meeting notes from dloeffel@highlandsresidential.com before 2026-01-16
        and_(
            EmailCache.sender_email == LEGACY_MEETING_NOTES_SENDER,
            EmailCache.subject.like(f"{LEGACY_MEETING_NOTES_PREFIX}%"),  # Case sensitive
            EmailCache.received_at < LEGACY_MEETING_NOTES_CUTOFF,
        ),
    ]

    # Add filter for emails with the Plaud Gmail label
    if plaud_label_id:
        conditions.append(EmailCache.labels.any(plaud_label_id))

    return or_(*conditions)


def _extract_meeting_title(subject: str, received_at: datetime) -> str:
    """Extract a clean title from a meeting notes email subject."""
    title = subject

    # Handle Plaud recordings: "Meeting Notes from Plaud: Title" or "Meeting Notes from Plaud - Title"
    if "Meeting Notes from Plaud" in title:
        title = title.replace("Meeting Notes from Plaud", "").strip()
        if title.startswith(":"):
            title = title[1:].strip()
        if title.startswith("-"):
            title = title[1:].strip()
        if not title:
            title = f"Plaud Recording - {received_at.strftime('%b %d, %Y')}"
    # Handle legacy meeting notes: "Meeting Notes: Title" or "Meeting Notes - Title"
    elif title.startswith(LEGACY_MEETING_NOTES_PREFIX):
        title = title[len(LEGACY_MEETING_NOTES_PREFIX):].strip()
        if title.startswith(":"):
            title = title[1:].strip()
        if title.startswith("-"):
            title = title[1:].strip()
        if not title:
            title = f"Meeting Notes - {received_at.strftime('%b %d, %Y')}"

    return title


@router.get("/plaud", response_model=list[PlaudRecordingListItem])
async def list_plaud_recordings(
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    limit: int = Query(default=20, le=100),
    search: str | None = Query(default=None),
) -> list[PlaudRecordingListItem]:
    """List Plaud recordings from email cache."""
    # Look up the Plaud label ID to include labeled emails
    plaud_label_id = await _get_plaud_label_id(db)

    query = (
        select(EmailCache)
        .where(_is_plaud_or_legacy_meeting_note(plaud_label_id))
        .order_by(EmailCache.received_at.desc())
        .limit(limit)
    )

    if search:
        query = query.where(
            EmailCache.body_text.ilike(f"%{search}%")
            | EmailCache.subject.ilike(f"%{search}%")
        )

    result = await db.execute(query)
    emails = result.scalars().all()

    recordings = []
    for email in emails:
        title = _extract_meeting_title(email.subject, email.received_at)

        recordings.append(
            PlaudRecordingListItem(
                id=email.id,
                email_id=email.gmail_id,
                title=title,
                date=email.received_at,
                sender=email.sender_name or email.sender_email,
                summary=email.summary or email.snippet,
                has_content=bool(email.body_text),
            )
        )

    return recordings


@router.get("/plaud/{recording_id}", response_model=PlaudRecordingDetail)
async def get_plaud_recording(
    recording_id: int,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> PlaudRecordingDetail:
    """Get full Plaud recording details."""
    # Look up the Plaud label ID to include labeled emails
    plaud_label_id = await _get_plaud_label_id(db)

    result = await db.execute(
        select(EmailCache).where(
            EmailCache.id == recording_id,
            _is_plaud_or_legacy_meeting_note(plaud_label_id),
        )
    )
    email = result.scalar_one_or_none()

    if not email:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Meeting notes not found",
        )

    # Extract a cleaner title
    title = _extract_meeting_title(email.subject, email.received_at)

    return PlaudRecordingDetail(
        id=email.id,
        email_id=email.gmail_id,
        title=title,
        date=email.received_at,
        sender=email.sender_name or email.sender_email,
        summary=email.summary,
        body_text=email.body_text,
        action_items=email.action_items,
    )


# ============== Unified Meetings List ==============
# NOTE: These routes must come BEFORE /{meeting_id} to avoid route conflicts


@router.get("/unified", response_model=list[UnifiedMeetingItem])
async def list_unified_meetings(
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    limit: int = Query(default=20, le=100),
    source: str = Query(default="all"),  # "all", "fireflies", "plaud"
    search: str | None = Query(default=None),
) -> list[UnifiedMeetingItem]:
    """List both Fireflies meetings and Plaud recordings in a unified view."""
    items: list[UnifiedMeetingItem] = []

    # Fetch Fireflies meetings
    if source in ("all", "fireflies"):
        service = get_fireflies_service()
        if service.is_configured:
            try:
                if search:
                    meetings = await service.search_meetings(
                        search_query=search, limit=limit
                    )
                else:
                    meetings = await service.list_recent_meetings(limit=limit)

                for m in meetings:
                    meeting_date = None
                    if m.get("date"):
                        try:
                            parsed_date = datetime.fromisoformat(
                                m["date"].replace("Z", "+00:00")
                            )
                            # Convert to naive UTC for consistent comparison
                            meeting_date = parsed_date.replace(tzinfo=None)
                        except ValueError:
                            pass

                    items.append(
                        UnifiedMeetingItem(
                            id=m["id"],
                            source="fireflies",
                            title=m["title"],
                            date=meeting_date,
                            duration_minutes=m.get("duration_minutes"),
                            participants=m.get("participants", []),
                            summary_preview=m.get("summary_preview"),
                        )
                    )
            except Exception:
                pass  # Silently skip Fireflies errors for unified view

    # Fetch Plaud recordings
    if source in ("all", "plaud"):
        plaud_label_id = await _get_plaud_label_id(db)
        query = (
            select(EmailCache)
            .where(_is_plaud_or_legacy_meeting_note(plaud_label_id))
            .order_by(EmailCache.received_at.desc())
            .limit(limit)
        )

        if search:
            query = query.where(
                EmailCache.body_text.ilike(f"%{search}%")
                | EmailCache.subject.ilike(f"%{search}%")
            )

        result = await db.execute(query)
        emails = result.scalars().all()

        for email in emails:
            title = _extract_meeting_title(email.subject, email.received_at)
            items.append(
                UnifiedMeetingItem(
                    id=f"plaud_{email.id}",
                    source="plaud",
                    title=title,
                    date=email.received_at,
                    sender=email.sender_name or email.sender_email,
                    summary_preview=email.summary or email.snippet,
                )
            )

    # Sort by date descending (most recent first), with None dates at the end
    # Normalize to naive UTC for comparison to handle mixed tz-aware/naive dates
    def sort_key(x: UnifiedMeetingItem) -> tuple[bool, datetime]:
        if x.date is None:
            return (True, datetime.min)
        # Convert to naive UTC if timezone-aware
        d = x.date
        if d.tzinfo is not None:
            d = d.replace(tzinfo=None)
        return (False, d)

    items.sort(key=sort_key, reverse=True)

    # Limit total results
    return items[:limit]


@router.post("/unified/sync", response_model=UnifiedSyncResponse)
async def sync_unified_meetings(
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    limit: int = Query(default=20, le=50),
) -> UnifiedSyncResponse:
    """Sync both Fireflies meetings and Plaud recordings."""
    fireflies_synced = 0
    fireflies_new = 0
    fireflies_updated = 0
    plaud_synced = 0
    fireflies_error: str | None = None
    plaud_error: str | None = None

    # Sync Fireflies
    service = get_fireflies_service()
    if service.is_configured:
        try:
            meetings = await service.list_recent_meetings(limit=limit)

            for meeting_data in meetings:
                fireflies_id = meeting_data["id"]

                result = await db.execute(
                    select(MeetingNote).where(MeetingNote.fireflies_id == fireflies_id)
                )
                existing = result.scalar_one_or_none()

                meeting_date = None
                if meeting_data.get("date"):
                    try:
                        parsed_date = datetime.fromisoformat(
                            meeting_data["date"].replace("Z", "+00:00")
                        )
                        # Convert to naive UTC for database storage
                        meeting_date = parsed_date.replace(tzinfo=None)
                    except ValueError:
                        pass

                if existing:
                    existing.title = meeting_data["title"]
                    existing.meeting_date = meeting_date
                    existing.duration_minutes = meeting_data.get("duration_minutes")
                    existing.participants = meeting_data.get("participants")
                    existing.last_synced_at = datetime.utcnow()
                    fireflies_updated += 1
                else:
                    meeting_note = MeetingNote(
                        user_id=user.id,
                        fireflies_id=fireflies_id,
                        title=meeting_data["title"],
                        meeting_date=meeting_date,
                        duration_minutes=meeting_data.get("duration_minutes"),
                        participants=meeting_data.get("participants"),
                        last_synced_at=datetime.utcnow(),
                    )
                    db.add(meeting_note)
                    fireflies_new += 1

            await db.commit()
            fireflies_synced = len(meetings)
        except Exception as e:
            await db.rollback()
            fireflies_error = str(e)

    # Sync Plaud recordings
    try:
        from sage.core.email_processor import EmailProcessor

        query = f"label:{PLAUD_GMAIL_LABEL}"
        processor = EmailProcessor(db)
        plaud_synced = await processor.sync_emails_by_query(query=query, max_results=100)
    except Exception as e:
        plaud_error = str(e)

    return UnifiedSyncResponse(
        fireflies_synced=fireflies_synced,
        fireflies_new=fireflies_new,
        fireflies_updated=fireflies_updated,
        plaud_synced=plaud_synced,
        fireflies_error=fireflies_error,
        plaud_error=plaud_error,
    )


# ============== Fireflies Meeting Details ==============
# NOTE: Dynamic routes must come AFTER static routes


@router.get("/{meeting_id}", response_model=MeetingDetail)
async def get_meeting_detail(
    meeting_id: str,
    user: Annotated[User, Depends(get_current_user)],
) -> MeetingDetail:
    """Get full meeting details including transcript."""
    service = get_fireflies_service()

    if not service.is_configured:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Fireflies integration not configured",
        )

    try:
        meeting = await service.get_meeting_transcript(meeting_id)
        if not meeting:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Meeting {meeting_id} not found",
            )
        return MeetingDetail(**meeting)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to fetch meeting: {str(e)}",
        )


@router.get("/{meeting_id}/summary", response_model=MeetingSummary)
async def get_meeting_summary(
    meeting_id: str,
    user: Annotated[User, Depends(get_current_user)],
) -> MeetingSummary:
    """Get meeting summary without full transcript."""
    service = get_fireflies_service()

    if not service.is_configured:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Fireflies integration not configured",
        )

    try:
        summary = await service.get_meeting_summary(meeting_id)
        if not summary:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Meeting {meeting_id} not found",
            )
        return MeetingSummary(**summary)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to fetch meeting summary: {str(e)}",
        )


@router.post("/{meeting_id}/cache", response_model=MeetingNoteResponse)
async def cache_meeting_details(
    meeting_id: str,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> MeetingNoteResponse:
    """Cache full meeting details including summary and action items."""
    service = get_fireflies_service()

    if not service.is_configured:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Fireflies integration not configured",
        )

    try:
        # Fetch full meeting details
        meeting = await service.get_meeting_transcript(meeting_id)
        if not meeting:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Meeting {meeting_id} not found",
            )

        # Check if meeting already exists
        result = await db.execute(
            select(MeetingNote).where(MeetingNote.fireflies_id == meeting_id)
        )
        existing = result.scalar_one_or_none()

        # Parse date
        meeting_date = None
        if meeting.get("date"):
            try:
                parsed_date = datetime.fromisoformat(
                    meeting["date"].replace("Z", "+00:00")
                )
                # Convert to naive UTC for database storage
                meeting_date = parsed_date.replace(tzinfo=None)
            except ValueError:
                pass

        if existing:
            # Update existing record
            existing.title = meeting["title"]
            existing.meeting_date = meeting_date
            existing.duration_minutes = meeting.get("duration_minutes")
            existing.participants = meeting.get("participants")
            existing.summary = meeting.get("summary")
            existing.key_points = meeting.get("key_points")
            existing.action_items = meeting.get("action_items")
            existing.keywords = meeting.get("keywords")
            existing.transcript = meeting.get("transcript")
            existing.last_synced_at = datetime.utcnow()
            meeting_note = existing
        else:
            # Create new record
            meeting_note = MeetingNote(
                user_id=user.id,
                fireflies_id=meeting_id,
                title=meeting["title"],
                meeting_date=meeting_date,
                duration_minutes=meeting.get("duration_minutes"),
                participants=meeting.get("participants"),
                summary=meeting.get("summary"),
                key_points=meeting.get("key_points"),
                action_items=meeting.get("action_items"),
                keywords=meeting.get("keywords"),
                transcript=meeting.get("transcript"),
                last_synced_at=datetime.utcnow(),
            )
            db.add(meeting_note)

        await db.commit()
        await db.refresh(meeting_note)

        return MeetingNoteResponse.model_validate(meeting_note)
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to cache meeting: {str(e)}",
        )
