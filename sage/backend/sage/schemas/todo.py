"""Pydantic schemas for todo items."""

from datetime import datetime, date
from typing import Optional
from pydantic import BaseModel, Field

from sage.models.todo import TodoCategory, TodoPriority, TodoStatus


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


class TodoBase(BaseModel):
    """Base todo schema."""
    title: str = Field(..., max_length=500)
    description: Optional[str] = None
    category: TodoCategory
    priority: TodoPriority = TodoPriority.NORMAL
    due_date: Optional[date] = None


class TodoCreate(TodoBase):
    """Schema for creating a manual todo."""
    contact_name: Optional[str] = None
    contact_email: Optional[str] = None


class TodoUpdate(BaseModel):
    """Schema for updating a todo."""
    title: Optional[str] = Field(None, max_length=500)
    description: Optional[str] = None
    priority: Optional[TodoPriority] = None
    due_date: Optional[date] = None
    status: Optional[TodoStatus] = None


class TodoSnooze(BaseModel):
    """Schema for snoozing a todo."""
    snooze_until: date


class TodoComplete(BaseModel):
    """Schema for completing a todo."""
    reason: str = "Completed"


class TodoResponse(TodoBase):
    """Schema for todo response."""
    id: int
    status: TodoStatus
    source_type: str
    source_id: Optional[str] = None
    source_summary: Optional[str] = None
    contact_name: Optional[str] = None
    contact_email: Optional[str] = None
    snoozed_until: Optional[date] = None
    detection_confidence: Optional[float] = None
    detected_deadline_text: Optional[str] = None
    completed_at: Optional[datetime] = None
    completed_reason: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    # Source email summary (populated on detail view)
    source_email: Optional[SourceEmailSummary] = None

    class Config:
        from_attributes = True


class TodoListResponse(BaseModel):
    """Response for listing todos."""
    todos: list[TodoResponse]
    total: int


class TodoGroupedResponse(BaseModel):
    """Response for grouped todos."""
    due_today: list[TodoResponse]
    due_this_week: list[TodoResponse]
    overdue: list[TodoResponse]
    no_deadline: list[TodoResponse]
    completed_recently: list[TodoResponse]  # Last 7 days
    total_pending: int
    total_overdue: int


class TodoScanRequest(BaseModel):
    """Request to scan emails for todos."""
    since_days: int = Field(default=180, ge=1, le=365, description="Scan emails from the last N days")
    limit: Optional[int] = Field(default=None, ge=1, description="Maximum emails to scan")


class TodoScanProgress(BaseModel):
    """Progress of todo scanning."""
    total_emails: int
    scanned: int
    todos_created: int
    duplicates_skipped: int
    filtered_out: int
    errors: int
    by_category: dict[str, int]
    status: str = "in_progress"  # in_progress, completed, failed


class TodoScanResponse(BaseModel):
    """Response for scan initiation."""
    scan_id: str
    message: str
    status: str
