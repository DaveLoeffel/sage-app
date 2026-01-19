"""Meeting schemas for API responses."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict


class MeetingListItem(BaseModel):
    """Meeting summary for list views."""

    id: str
    title: str
    date: str | None
    duration_minutes: int | None
    participants: list[str]
    summary_preview: str | None = None

    model_config = ConfigDict(from_attributes=True)


class TranscriptEntry(BaseModel):
    """Single transcript entry."""

    speaker: str
    text: str
    timestamp: float | None = None


class MeetingDetail(BaseModel):
    """Full meeting details including transcript."""

    id: str
    title: str
    date: str | None
    duration_minutes: int | None
    participants: list[str]
    summary: str | None = None
    key_points: list[str] = []
    action_items: list[str] = []
    keywords: list[str] = []
    transcript: list[TranscriptEntry] = []

    model_config = ConfigDict(from_attributes=True)


class MeetingSummary(BaseModel):
    """Meeting summary without full transcript."""

    id: str
    title: str
    date: str | None
    overview: str | None = None
    key_points: list[str] = []
    action_items: list[str] = []
    keywords: list[str] = []
    outline: list[str] = []

    model_config = ConfigDict(from_attributes=True)


class MeetingNoteResponse(BaseModel):
    """Cached meeting note response."""

    id: int
    fireflies_id: str
    title: str
    meeting_date: datetime | None
    duration_minutes: int | None
    participants: list[str] | None
    summary: str | None
    key_points: list[str] | None
    action_items: list[str] | None
    keywords: list[str] | None
    last_synced_at: datetime
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class MeetingSearchParams(BaseModel):
    """Parameters for meeting search."""

    query: str = ""
    participant_email: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    limit: int = 10


class MeetingSyncResponse(BaseModel):
    """Response for meeting sync operation."""

    synced_count: int
    new_count: int
    updated_count: int


class PlaudRecordingListItem(BaseModel):
    """Plaud recording summary for list views."""

    id: int
    email_id: str
    title: str
    date: datetime
    sender: str
    summary: str | None = None
    has_content: bool = True

    model_config = ConfigDict(from_attributes=True)


class PlaudRecordingDetail(BaseModel):
    """Full Plaud recording details."""

    id: int
    email_id: str
    title: str
    date: datetime
    sender: str
    summary: str | None = None
    body_text: str | None = None
    action_items: str | None = None

    model_config = ConfigDict(from_attributes=True)


class UnifiedMeetingItem(BaseModel):
    """Unified meeting item for combined Fireflies/Plaud list views."""

    id: str  # Fireflies ID or "plaud_{id}"
    source: Literal["fireflies", "plaud"]
    title: str
    date: datetime | None
    duration_minutes: int | None = None  # Fireflies only
    participants: list[str] = []  # Fireflies only
    sender: str | None = None  # Plaud only
    summary_preview: str | None = None


class UnifiedSyncResponse(BaseModel):
    """Response for unified sync operation."""

    fireflies_synced: int
    fireflies_new: int
    fireflies_updated: int
    plaud_synced: int
    fireflies_error: str | None = None
    plaud_error: str | None = None
