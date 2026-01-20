"""Todo item tracking API endpoints."""

from datetime import datetime, date, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from sage.services.database import get_db
from sage.models.todo import TodoItem, TodoCategory, TodoPriority, TodoStatus
from sage.models.email import EmailCache
from sage.models.user import User
from sage.schemas.todo import (
    TodoCreate,
    TodoUpdate,
    TodoSnooze,
    TodoComplete,
    TodoResponse,
    TodoListResponse,
    TodoGroupedResponse,
    TodoScanRequest,
    TodoScanProgress,
    TodoScanResponse,
    SourceEmailSummary,
)
from sage.schemas.email import DraftReplyResponse
from sage.core.claude_agent import get_claude_agent

router = APIRouter()

# In-memory storage for scan progress
_scan_progress: dict[str, TodoScanProgress] = {}


def todo_to_response(
    todo: TodoItem,
    source_email: EmailCache | None = None,
) -> TodoResponse:
    """Convert TodoItem model to response schema."""
    response = TodoResponse.model_validate(todo)

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


@router.get("", response_model=TodoListResponse)
async def list_todos(
    db: Annotated[AsyncSession, Depends(get_db)],
    status: TodoStatus | None = None,
    category: TodoCategory | None = None,
    priority: TodoPriority | None = None,
    contact_email: str | None = None,
    include_completed: bool = False,
) -> TodoListResponse:
    """List todos with filtering."""
    query = select(TodoItem).order_by(TodoItem.due_date.nulls_last(), TodoItem.priority.desc())

    # Apply filters
    if status:
        query = query.where(TodoItem.status == status)
    elif not include_completed:
        # Default: exclude completed and cancelled
        query = query.where(
            TodoItem.status.in_([TodoStatus.PENDING, TodoStatus.SNOOZED])
        )

    if category:
        query = query.where(TodoItem.category == category)
    if priority:
        query = query.where(TodoItem.priority == priority)
    if contact_email:
        query = query.where(TodoItem.contact_email == contact_email)

    result = await db.execute(query)
    todos = result.scalars().all()

    return TodoListResponse(
        todos=[todo_to_response(t) for t in todos],
        total=len(todos),
    )


@router.get("/grouped", response_model=TodoGroupedResponse)
async def get_grouped_todos(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TodoGroupedResponse:
    """Get todos grouped by due date status."""
    today = date.today()
    week_end = today + timedelta(days=7)
    week_ago = today - timedelta(days=7)

    # Get all pending/snoozed todos
    query = select(TodoItem).where(
        TodoItem.status.in_([TodoStatus.PENDING, TodoStatus.SNOOZED])
    ).order_by(TodoItem.due_date.nulls_last(), TodoItem.priority.desc())

    result = await db.execute(query)
    todos = result.scalars().all()

    # Group todos
    due_today = []
    due_this_week = []
    overdue = []
    no_deadline = []

    for todo in todos:
        if todo.due_date is None:
            no_deadline.append(todo_to_response(todo))
        elif todo.due_date < today:
            overdue.append(todo_to_response(todo))
        elif todo.due_date == today:
            due_today.append(todo_to_response(todo))
        elif todo.due_date <= week_end:
            due_this_week.append(todo_to_response(todo))
        else:
            # Future todos go in no_deadline for now
            no_deadline.append(todo_to_response(todo))

    # Get recently completed (last 7 days)
    completed_query = select(TodoItem).where(
        and_(
            TodoItem.status == TodoStatus.COMPLETED,
            TodoItem.completed_at >= datetime.combine(week_ago, datetime.min.time()),
        )
    ).order_by(TodoItem.completed_at.desc()).limit(20)

    completed_result = await db.execute(completed_query)
    completed_recently = [todo_to_response(t) for t in completed_result.scalars().all()]

    return TodoGroupedResponse(
        due_today=due_today,
        due_this_week=due_this_week,
        overdue=overdue,
        no_deadline=no_deadline,
        completed_recently=completed_recently,
        total_pending=len(due_today) + len(due_this_week) + len(no_deadline),
        total_overdue=len(overdue),
    )


# =============================================================================
# SCAN ENDPOINTS (must come before parametric routes)
# =============================================================================

@router.post("/scan", response_model=TodoScanResponse)
async def scan_emails_for_todos(
    db: Annotated[AsyncSession, Depends(get_db)],
    user_email: str = Query(..., description="User's email address"),
    since_days: int = Query(180, ge=1, le=365, description="Scan emails from the last N days"),
    limit: int | None = Query(None, ge=1, description="Maximum emails to scan"),
) -> TodoScanResponse:
    """
    Scan emails for todo items.

    Analyzes emails to find:
    - Self-reminders (emails to self)
    - Requests received (someone asks Dave to do something)
    - Commitments made (Dave promises to do something)

    This runs asynchronously. Use /scan/{scan_id} to check progress.
    """
    import asyncio
    from sage.services.todo_detector import TodoDetector, load_vip_contacts

    scan_id = f"scan_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    _scan_progress[scan_id] = TodoScanProgress(
        total_emails=0,
        scanned=0,
        todos_created=0,
        duplicates_skipped=0,
        filtered_out=0,
        errors=0,
        by_category={},
        status="in_progress",
    )

    async def run_scan():
        try:
            # Get user
            user_result = await db.execute(select(User).where(User.email == user_email))
            user = user_result.scalar_one_or_none()

            if not user:
                _scan_progress[scan_id] = TodoScanProgress(
                    total_emails=0,
                    scanned=0,
                    todos_created=0,
                    duplicates_skipped=0,
                    filtered_out=0,
                    errors=1,
                    by_category={},
                    status="failed",
                )
                return

            # Load VIP contacts
            vip_contacts = await load_vip_contacts(db, user.id)

            # Initialize detector
            detector = TodoDetector(user_email, vip_contacts)

            # Calculate since_date
            since_date = date.today() - timedelta(days=since_days)

            # Run scan
            progress = await detector.scan_emails(db, user.id, since_date, limit)

            _scan_progress[scan_id] = TodoScanProgress(
                total_emails=progress.total_emails,
                scanned=progress.scanned,
                todos_created=progress.todos_created,
                duplicates_skipped=progress.duplicates_skipped,
                filtered_out=progress.filtered_out,
                errors=progress.errors,
                by_category=progress.by_category,
                status="completed",
            )

        except Exception as e:
            import traceback
            traceback.print_exc()
            _scan_progress[scan_id] = TodoScanProgress(
                total_emails=0,
                scanned=0,
                todos_created=0,
                duplicates_skipped=0,
                filtered_out=0,
                errors=1,
                by_category={},
                status="failed",
            )

    asyncio.create_task(run_scan())

    return TodoScanResponse(
        scan_id=scan_id,
        message="Todo scan started",
        status="in_progress",
    )


@router.get("/scan/{scan_id}", response_model=TodoScanProgress)
async def get_scan_progress(scan_id: str) -> TodoScanProgress:
    """Get the progress of a todo scanning operation."""
    if scan_id not in _scan_progress:
        raise HTTPException(status_code=404, detail="Scan not found")

    return _scan_progress[scan_id]


@router.get("/overdue", response_model=list[TodoResponse])
async def get_overdue_todos(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[TodoResponse]:
    """Get all overdue todos."""
    today = date.today()
    query = select(TodoItem).where(
        and_(
            TodoItem.status == TodoStatus.PENDING,
            TodoItem.due_date < today,
        )
    ).order_by(TodoItem.due_date)

    result = await db.execute(query)
    todos = result.scalars().all()

    return [todo_to_response(t) for t in todos]


@router.get("/due-today", response_model=list[TodoResponse])
async def get_due_today_todos(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[TodoResponse]:
    """Get todos due today."""
    today = date.today()
    query = select(TodoItem).where(
        and_(
            TodoItem.status == TodoStatus.PENDING,
            TodoItem.due_date == today,
        )
    ).order_by(TodoItem.priority.desc())

    result = await db.execute(query)
    todos = result.scalars().all()

    return [todo_to_response(t) for t in todos]


# =============================================================================
# STANDARD TODO ENDPOINTS
# =============================================================================

@router.get("/{todo_id}", response_model=TodoResponse)
async def get_todo(
    todo_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TodoResponse:
    """Get a specific todo by ID with source email data."""
    result = await db.execute(select(TodoItem).where(TodoItem.id == todo_id))
    todo = result.scalar_one_or_none()

    if not todo:
        raise HTTPException(status_code=404, detail="Todo not found")

    # Fetch source email if this is an email-based todo
    source_email = None
    if todo.source_type == "email" and todo.source_id:
        email_result = await db.execute(
            select(EmailCache).where(EmailCache.gmail_id == todo.source_id)
        )
        source_email = email_result.scalar_one_or_none()

    return todo_to_response(todo, source_email)


@router.post("", response_model=TodoResponse)
async def create_todo(
    todo_data: TodoCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TodoResponse:
    """Create a new manual todo."""
    # Get the first user (single-user setup)
    user_result = await db.execute(select(User).limit(1))
    user = user_result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=400, detail="No user found. Please authenticate first.")

    todo = TodoItem(
        user_id=user.id,
        title=todo_data.title,
        description=todo_data.description,
        category=todo_data.category,
        priority=todo_data.priority,
        status=TodoStatus.PENDING,
        due_date=todo_data.due_date,
        source_type="manual",
        source_id=None,
        source_summary="Manually created",
        contact_name=todo_data.contact_name,
        contact_email=todo_data.contact_email,
    )

    db.add(todo)
    await db.commit()
    await db.refresh(todo)

    return todo_to_response(todo)


@router.patch("/{todo_id}", response_model=TodoResponse)
async def update_todo(
    todo_id: int,
    update_data: TodoUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TodoResponse:
    """Update a todo."""
    result = await db.execute(select(TodoItem).where(TodoItem.id == todo_id))
    todo = result.scalar_one_or_none()

    if not todo:
        raise HTTPException(status_code=404, detail="Todo not found")

    # Update fields
    update_dict = update_data.model_dump(exclude_unset=True)
    for field, value in update_dict.items():
        setattr(todo, field, value)

    await db.commit()
    await db.refresh(todo)

    return todo_to_response(todo)


@router.post("/{todo_id}/complete", response_model=TodoResponse)
async def complete_todo(
    todo_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    reason: str = Query("Completed"),
) -> TodoResponse:
    """Mark a todo as completed."""
    result = await db.execute(select(TodoItem).where(TodoItem.id == todo_id))
    todo = result.scalar_one_or_none()

    if not todo:
        raise HTTPException(status_code=404, detail="Todo not found")

    todo.mark_completed(reason)
    await db.commit()
    await db.refresh(todo)

    return todo_to_response(todo)


@router.post("/{todo_id}/snooze", response_model=TodoResponse)
async def snooze_todo(
    todo_id: int,
    snooze_data: TodoSnooze,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TodoResponse:
    """Snooze a todo until a later date."""
    result = await db.execute(select(TodoItem).where(TodoItem.id == todo_id))
    todo = result.scalar_one_or_none()

    if not todo:
        raise HTTPException(status_code=404, detail="Todo not found")

    todo.snooze(snooze_data.snooze_until)
    await db.commit()
    await db.refresh(todo)

    return todo_to_response(todo)


@router.post("/{todo_id}/cancel", response_model=TodoResponse)
async def cancel_todo(
    todo_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    reason: str = Query("Cancelled"),
) -> TodoResponse:
    """Cancel a todo."""
    result = await db.execute(select(TodoItem).where(TodoItem.id == todo_id))
    todo = result.scalar_one_or_none()

    if not todo:
        raise HTTPException(status_code=404, detail="Todo not found")

    todo.mark_cancelled(reason)
    await db.commit()
    await db.refresh(todo)

    return todo_to_response(todo)


@router.delete("/{todo_id}")
async def delete_todo(
    todo_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """Delete a todo."""
    result = await db.execute(select(TodoItem).where(TodoItem.id == todo_id))
    todo = result.scalar_one_or_none()

    if not todo:
        raise HTTPException(status_code=404, detail="Todo not found")

    await db.delete(todo)
    await db.commit()

    return {"message": "Todo deleted successfully"}


@router.post("/{todo_id}/draft-email", response_model=DraftReplyResponse)
async def generate_todo_draft_email(
    todo_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> DraftReplyResponse:
    """
    Generate a draft email response for a todo item.

    Best for REQUEST_RECEIVED or COMMITMENT_MADE todos where the user
    needs to respond to the request or follow up on their commitment.
    """
    # Fetch todo
    result = await db.execute(select(TodoItem).where(TodoItem.id == todo_id))
    todo = result.scalar_one_or_none()

    if not todo:
        raise HTTPException(status_code=404, detail="Todo not found")

    # Check if this is an appropriate type for drafting
    if todo.category not in [TodoCategory.REQUEST_RECEIVED, TodoCategory.COMMITMENT_MADE]:
        raise HTTPException(
            status_code=400,
            detail="Draft email is only available for REQUEST_RECEIVED or COMMITMENT_MADE todos"
        )

    # Fetch source email if available
    source_email = None
    if todo.source_type == "email" and todo.source_id:
        email_result = await db.execute(
            select(EmailCache).where(EmailCache.gmail_id == todo.source_id)
        )
        source_email = email_result.scalar_one_or_none()

    # Generate draft using Claude
    agent = await get_claude_agent()
    draft = await agent.generate_todo_response(
        todo_title=todo.title,
        todo_category=todo.category.value,
        contact_name=todo.contact_name,
        contact_email=todo.contact_email,
        source_email_subject=source_email.subject if source_email else None,
        source_email_body=source_email.body_text if source_email else None,
        todo_description=todo.description,
    )

    return draft
