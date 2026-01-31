"""Chat schemas."""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel


class MessageRole(str, Enum):
    """Chat message role."""

    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class ChatMessage(BaseModel):
    """Schema for a chat message."""

    role: MessageRole
    content: str
    timestamp: datetime | None = None


class ChatRequest(BaseModel):
    """Schema for chat request."""

    message: str
    conversation_id: str | None = None
    context: dict | None = None  # Additional context like current email, followup, etc.


class ChatResponse(BaseModel):
    """Schema for chat response."""

    message: str
    conversation_id: str
    tool_calls: list[dict] | None = None  # MCP tool calls made
    suggestions: list[str] | None = None  # Suggested follow-up questions
    pending_approvals: list[dict] | None = None  # Actions awaiting user approval
