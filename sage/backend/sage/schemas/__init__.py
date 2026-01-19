"""Pydantic schemas for API validation."""

from sage.schemas.user import UserCreate, UserResponse, UserUpdate, TokenResponse
from sage.schemas.email import (
    EmailResponse,
    EmailListResponse,
    EmailAnalysis,
    DraftReplyRequest,
    DraftReplyResponse,
)
from sage.schemas.followup import (
    FollowupCreate,
    FollowupUpdate,
    FollowupResponse,
    FollowupListResponse,
)
from sage.schemas.chat import ChatRequest, ChatResponse, ChatMessage
from sage.schemas.dashboard import DashboardSummary
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

__all__ = [
    "UserCreate",
    "UserResponse",
    "UserUpdate",
    "TokenResponse",
    "EmailResponse",
    "EmailListResponse",
    "EmailAnalysis",
    "DraftReplyRequest",
    "DraftReplyResponse",
    "FollowupCreate",
    "FollowupUpdate",
    "FollowupResponse",
    "FollowupListResponse",
    "ChatRequest",
    "ChatResponse",
    "ChatMessage",
    "DashboardSummary",
    "MeetingListItem",
    "MeetingDetail",
    "MeetingSummary",
    "MeetingNoteResponse",
    "MeetingSyncResponse",
    "PlaudRecordingListItem",
    "PlaudRecordingDetail",
    "UnifiedMeetingItem",
    "UnifiedSyncResponse",
]
