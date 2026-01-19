"""Follow-up tracking API endpoints."""

from datetime import datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from sage.services.database import get_db
from sage.models.followup import Followup, FollowupStatus, FollowupPriority
from sage.models.user import User
from sage.schemas.followup import (
    FollowupCreate,
    FollowupUpdate,
    FollowupResponse,
    FollowupListResponse,
)

router = APIRouter()


def compute_followup_response(followup: Followup) -> FollowupResponse:
    """Compute additional fields for followup response."""
    now = datetime.utcnow()
    is_overdue = followup.status in [FollowupStatus.PENDING, FollowupStatus.REMINDED] and followup.due_date < now
    days_until_due = (followup.due_date - now).days if followup.due_date > now else None

    response = FollowupResponse.model_validate(followup)
    response.is_overdue = is_overdue
    response.days_until_due = days_until_due
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
    """Get a specific follow-up by ID."""
    result = await db.execute(select(Followup).where(Followup.id == followup_id))
    followup = result.scalar_one_or_none()

    if not followup:
        raise HTTPException(status_code=404, detail="Follow-up not found")

    return compute_followup_response(followup)


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
