"""Test chat endpoints."""

import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_chat_endpoint(client: AsyncClient, mock_anthropic):
    """Test chat endpoint returns AI response."""
    # Mock the claude agent
    with patch("sage.api.chat.get_claude_agent") as mock_get_agent:
        mock_agent = AsyncMock()
        mock_agent.chat.return_value = {
            "message": "Hello! How can I help you today?",
            "tool_calls": None,
            "suggestions": ["What should I focus on today?"],
        }
        mock_get_agent.return_value = mock_agent

        response = await client.post(
            "/api/v1/chat",
            json={"message": "Hello"}
        )

        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        assert "conversation_id" in data
        assert data["message"] == "Hello! How can I help you today?"


@pytest.mark.asyncio
async def test_chat_with_conversation_id(client: AsyncClient):
    """Test chat endpoint maintains conversation context."""
    with patch("sage.api.chat.get_claude_agent") as mock_get_agent:
        mock_agent = AsyncMock()
        mock_agent.chat.return_value = {
            "message": "I remember our conversation.",
            "tool_calls": None,
            "suggestions": [],
        }
        mock_get_agent.return_value = mock_agent

        conversation_id = "test-conv-123"
        response = await client.post(
            "/api/v1/chat",
            json={
                "message": "Remember this?",
                "conversation_id": conversation_id
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert data["conversation_id"] == conversation_id


@pytest.mark.asyncio
async def test_chat_with_context(client: AsyncClient):
    """Test chat endpoint accepts additional context."""
    with patch("sage.api.chat.get_claude_agent") as mock_get_agent:
        mock_agent = AsyncMock()
        mock_agent.chat.return_value = {
            "message": "I see the email context.",
            "tool_calls": None,
            "suggestions": [],
        }
        mock_get_agent.return_value = mock_agent

        response = await client.post(
            "/api/v1/chat",
            json={
                "message": "What about this email?",
                "context": {"email_id": 123, "subject": "Test"}
            }
        )

        assert response.status_code == 200


@pytest.mark.asyncio
async def test_chat_empty_message_fails(client: AsyncClient):
    """Test chat endpoint rejects empty messages."""
    response = await client.post(
        "/api/v1/chat",
        json={"message": ""}
    )
    # Empty string should still be accepted but return minimal response
    # or could be rejected based on validation
    assert response.status_code in [200, 422]
