"""Follow-up tracking API endpoints."""

from datetime import datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from sage.services.database import get_db, async_session_maker
from sage.models.followup import Followup, FollowupStatus, FollowupPriority
from sage.models.email import EmailCache
from sage.models.user import User
from sage.schemas.followup import (
    FollowupCreate,
    FollowupUpdate,
    FollowupResponse,
    FollowupListResponse,
    FollowupDetectionProgress,
    WaitingThreadResponse,
    DailyReviewItem,
    SourceEmailSummary,
)
from sage.schemas.email import DraftReplyResponse
from sage.core.claude_agent import get_claude_agent

router = APIRouter()

# In-memory storage for detection progress
_detection_progress: dict[str, FollowupDetectionProgress] = {}


def compute_followup_response(
    followup: Followup,
    source_email: EmailCache | None = None,
) -> FollowupResponse:
    """Compute additional fields for followup response."""
    now = datetime.utcnow()
    is_overdue = followup.status in [FollowupStatus.PENDING, FollowupStatus.REMINDED] and followup.due_date < now
    days_until_due = (followup.due_date - now).days if followup.due_date > now else None

    response = FollowupResponse.model_validate(followup)
    response.is_overdue = is_overdue
    response.days_until_due = days_until_due

    # Add source email summary if available
    if source_email:
        response.source_email = SourceEmailSummary(
            id=source_email.id,
            gmail_id=source_email.gmail_id,
            subject=source_email.subject,
            sender_email=source_email.sender_email,
            sender_name=source_email.sender_name,
            received_at=source_email.received_at,
            snippet=source_email.snippet,
            body_text=source_email.body_text,
        )

    return response


@router.get("", response_model=FollowupListResponse)
async def list_followups(
    db: Annotated[AsyncSession, Depends(get_db)],
    status: FollowupStatus | None = None,
    priority: FollowupPriority | None = None,
    contact_email: str | None = None,
    overdue_only: bool = False,
) -> FollowupListResponse:
    """List follow-ups with filtering."""
    query = select(Followup).order_by(Followup.due_date)

    # Apply filters
    if status:
        query = query.where(Followup.status == status)
    else:
        # Default: exclude completed and cancelled
        query = query.where(
            Followup.status.in_([
                FollowupStatus.PENDING,
                FollowupStatus.REMINDED,
                FollowupStatus.ESCALATED,
            ])
        )

    if priority:
        query = query.where(Followup.priority == priority)
    if contact_email:
        query = query.where(Followup.contact_email == contact_email)
    if overdue_only:
        query = query.where(Followup.due_date < datetime.utcnow())

    result = await db.execute(query)
    followups = result.scalars().all()

    # Compute counts
    now = datetime.utcnow()
    pending_count = sum(1 for f in followups if f.status == FollowupStatus.PENDING)
    overdue_count = sum(
        1 for f in followups
        if f.status in [FollowupStatus.PENDING, FollowupStatus.REMINDED]
        and f.due_date < now
    )

    return FollowupListResponse(
        followups=[compute_followup_response(f) for f in followups],
        total=len(followups),
        pending_count=pending_count,
        overdue_count=overdue_count,
    )


# =============================================================================
# DETECTION ENDPOINTS (must come before parametric routes)
# =============================================================================

@router.post("/detect", response_model=dict)
async def detect_followups(
    user_email: str = Query(..., description="User's email address"),
    months_back: int = Query(6, ge=1, le=12, description="Months of history to analyze"),
    use_ai: bool = Query(True, description="Use AI for ambiguous classifications"),
    seed_tracker: bool = Query(True, description="Create Followup records from detection"),
    max_followups: int = Query(100, ge=1, le=500, description="Max followups to create"),
) -> dict:
    """
    Detect email threads where user is waiting for a response.

    Analyzes sent emails to find threads awaiting response using:
    - Heuristic classification (fast, free)
    - AI classification for ambiguous cases (optional)

    Timing rules for suggested actions:
    - 1 business day: draft follow-up
    - 3 business days: send additional follow-up
    - 5+ business days: call + follow-up

    Can optionally seed the Followup tracker with detected threads.
    """
    import asyncio
    from sage.services.followup_detector import FollowupPatternDetector

    detection_id = f"detect_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    _detection_progress[detection_id] = FollowupDetectionProgress(
        status="running",
        phase="initializing",
        percent_complete=0,
    )

    async def run_detection():
        # Create a new database session for the background task
        # (the request session is invalid after the request returns)
        async with async_session_maker() as session:
            try:
                def progress_callback(phase: str, percent: int):
                    _detection_progress[detection_id] = FollowupDetectionProgress(
                        status="running",
                        phase=phase,
                        percent_complete=percent,
                    )

                detector = FollowupPatternDetector(user_email)
                result = await detector.detect(
                    session,
                    months_back=months_back,
                    use_ai=use_ai,
                    progress_callback=progress_callback,
                )

                followups_created = 0
                if seed_tracker:
                    # Get user
                    user_result = await session.execute(select(User).limit(1))
                    user = user_result.scalar_one_or_none()

                    if user:
                        followups_created, _ = await detector.seed_followup_tracker(
                            session, result, user.id, max_followups
                        )
                        await session.commit()

                _detection_progress[detection_id] = FollowupDetectionProgress(
                    status="completed",
                    phase="complete",
                    percent_complete=100,
                    threads_analyzed=result.threads_analyzed,
                    waiting_threads_found=len(result.waiting_threads),
                    followups_created=followups_created,
                    message=f"Found {len(result.waiting_threads)} threads awaiting response. "
                           f"Created {followups_created} followup records.",
                )

            except Exception as e:
                _detection_progress[detection_id] = FollowupDetectionProgress(
                    status="failed",
                    phase="error",
                    percent_complete=0,
                    error=str(e),
                )
                raise

    asyncio.create_task(run_detection())

    return {
        "detection_id": detection_id,
        "message": "Follow-up detection started",
        "status": "running",
        "progress_url": f"/api/v1/followups/detect/{detection_id}",
    }


@router.get("/detect/{detection_id}", response_model=FollowupDetectionProgress)
async def get_detection_progress(
    detection_id: str,
) -> FollowupDetectionProgress:
    """Get the progress of a follow-up detection operation."""
    if detection_id not in _detection_progress:
        raise HTTPException(status_code=404, detail="Detection not found")

    return _detection_progress[detection_id]


@router.get("/daily-review", response_model=list[DailyReviewItem])
async def get_daily_review(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[DailyReviewItem]:
    """
    Get follow-up items for daily review with contact phone numbers.

    Returns pending/reminded followups sorted by urgency,
    with suggested actions and contact phone numbers for calling.
    """
    from sage.services.followup_detector import FollowupPatternDetector
    from sage.models.contact import Contact

    # Get user
    user_result = await db.execute(select(User).limit(1))
    user = user_result.scalar_one_or_none()

    if not user:
        return []

    detector = FollowupPatternDetector(user.email)
    items = await detector.get_daily_review_items(db, user.id)

    return [DailyReviewItem(**item) for item in items]


# =============================================================================
# STANDARD FOLLOWUP ENDPOINTS
# =============================================================================

@router.get("/overdue", response_model=list[FollowupResponse])
async def get_overdue_followups(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[FollowupResponse]:
    """Get all overdue follow-ups."""
    now = datetime.utcnow()
    query = select(Followup).where(
        and_(
            Followup.status.in_([FollowupStatus.PENDING, FollowupStatus.REMINDED]),
            Followup.due_date < now,
        )
    ).order_by(Followup.due_date)

    result = await db.execute(query)
    followups = result.scalars().all()

    return [compute_followup_response(f) for f in followups]


@router.get("/due-today", response_model=list[FollowupResponse])
async def get_due_today(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[FollowupResponse]:
    """Get follow-ups due today."""
    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    today_end = today_start + timedelta(days=1)

    query = select(Followup).where(
        and_(
            Followup.status.in_([FollowupStatus.PENDING, FollowupStatus.REMINDED]),
            Followup.due_date >= today_start,
            Followup.due_date < today_end,
        )
    ).order_by(Followup.due_date)

    result = await db.execute(query)
    followups = result.scalars().all()

    return [compute_followup_response(f) for f in followups]


@router.get("/{followup_id}", response_model=FollowupResponse)
async def get_followup(
    followup_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> FollowupResponse:
    """Get a specific follow-up by ID with source email data."""
    result = await db.execute(select(Followup).where(Followup.id == followup_id))
    followup = result.scalar_one_or_none()

    if not followup:
        raise HTTPException(status_code=404, detail="Follow-up not found")

    # Fetch source email if email_id is set
    source_email = None
    if followup.email_id:
        email_result = await db.execute(
            select(EmailCache).where(EmailCache.id == followup.email_id)
        )
        source_email = email_result.scalar_one_or_none()

    # If no email_id, try to find by gmail_id
    if not source_email and followup.gmail_id:
        email_result = await db.execute(
            select(EmailCache).where(EmailCache.gmail_id == followup.gmail_id)
        )
        source_email = email_result.scalar_one_or_none()

    return compute_followup_response(followup, source_email)


@router.post("", response_model=FollowupResponse)
async def create_followup(
    followup_data: FollowupCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> FollowupResponse:
    """Create a new follow-up."""
    # Get the first user (single-user setup)
    user_result = await db.execute(select(User).limit(1))
    user = user_result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=400, detail="No user found. Please authenticate first.")

    followup = Followup(
        user_id=user.id,
        gmail_id=followup_data.gmail_id,
        thread_id=followup_data.thread_id,
        email_id=followup_data.email_id,
        subject=followup_data.subject,
        contact_email=followup_data.contact_email,
        contact_name=followup_data.contact_name,
        priority=followup_data.priority,
        due_date=followup_data.due_date,
        notes=followup_data.notes,
        escalation_email=followup_data.escalation_email,
        escalation_days=followup_data.escalation_days,
    )

    db.add(followup)
    await db.commit()
    await db.refresh(followup)

    return compute_followup_response(followup)


@router.patch("/{followup_id}", response_model=FollowupResponse)
async def update_followup(
    followup_id: int,
    update_data: FollowupUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> FollowupResponse:
    """Update a follow-up."""
    result = await db.execute(select(Followup).where(Followup.id == followup_id))
    followup = result.scalar_one_or_none()

    if not followup:
        raise HTTPException(status_code=404, detail="Follow-up not found")

    # Update fields
    update_dict = update_data.model_dump(exclude_unset=True)
    for field, value in update_dict.items():
        setattr(followup, field, value)

    await db.commit()
    await db.refresh(followup)

    return compute_followup_response(followup)


@router.post("/{followup_id}/complete", response_model=FollowupResponse)
async def complete_followup(
    followup_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    reason: str = Query("Manually completed"),
) -> FollowupResponse:
    """Mark a follow-up as completed."""
    result = await db.execute(select(Followup).where(Followup.id == followup_id))
    followup = result.scalar_one_or_none()

    if not followup:
        raise HTTPException(status_code=404, detail="Follow-up not found")

    followup.mark_completed(reason)
    await db.commit()
    await db.refresh(followup)

    return compute_followup_response(followup)


@router.post("/{followup_id}/cancel", response_model=FollowupResponse)
async def cancel_followup(
    followup_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    reason: str = Query("Cancelled by user"),
) -> FollowupResponse:
    """Cancel a follow-up."""
    result = await db.execute(select(Followup).where(Followup.id == followup_id))
    followup = result.scalar_one_or_none()

    if not followup:
        raise HTTPException(status_code=404, detail="Follow-up not found")

    followup.mark_cancelled(reason)
    await db.commit()
    await db.refresh(followup)

    return compute_followup_response(followup)


@router.delete("/{followup_id}")
async def delete_followup(
    followup_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """Delete a follow-up."""
    result = await db.execute(select(Followup).where(Followup.id == followup_id))
    followup = result.scalar_one_or_none()

    if not followup:
        raise HTTPException(status_code=404, detail="Follow-up not found")

    await db.delete(followup)
    await db.commit()

    return {"message": "Follow-up deleted successfully"}


@router.post("/{followup_id}/draft", response_model=DraftReplyResponse)
async def generate_followup_draft(
    followup_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> DraftReplyResponse:
    """
    Generate a draft follow-up email for a followup item.

    Uses Claude to generate a contextual follow-up reminder based on
    the original email thread and how long we've been waiting.
    """
    # Fetch followup
    result = await db.execute(select(Followup).where(Followup.id == followup_id))
    followup = result.scalar_one_or_none()

    if not followup:
        raise HTTPException(status_code=404, detail="Follow-up not found")

    # Fetch source email if available
    source_email = None
    if followup.email_id:
        email_result = await db.execute(
            select(EmailCache).where(EmailCache.id == followup.email_id)
        )
        source_email = email_result.scalar_one_or_none()

    if not source_email and followup.gmail_id:
        email_result = await db.execute(
            select(EmailCache).where(EmailCache.gmail_id == followup.gmail_id)
        )
        source_email = email_result.scalar_one_or_none()

    # Calculate days waiting
    now = datetime.utcnow()
    days_waiting = (now - followup.created_at).days

    # Generate draft using Claude
    agent = await get_claude_agent()
    draft = await agent.generate_followup_email(
        followup_subject=followup.subject,
        contact_name=followup.contact_name,
        contact_email=followup.contact_email,
        days_waiting=days_waiting,
        original_email_body=source_email.body_text if source_email else None,
        notes=followup.notes,
    )

    return draft
