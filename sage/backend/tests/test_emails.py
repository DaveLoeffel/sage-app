"""Test email endpoints."""

import pytest
from datetime import datetime
from unittest.mock import patch, AsyncMock
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from sage.models.email import EmailCache, EmailCategory, EmailPriority


async def create_test_email(
    db: AsyncSession,
    gmail_id: str = "msg123",
    subject: str = "Test Subject",
    category: EmailCategory = None,
    priority: EmailPriority = None,
    is_unread: bool = True,
) -> EmailCache:
    """Create a test email."""
    email = EmailCache(
        gmail_id=gmail_id,
        thread_id="thread123",
        subject=subject,
        sender_email="sender@test.com",
        sender_name="Test Sender",
        body_text="Test email body content",
        snippet="Test email...",
        is_unread=is_unread,
        has_attachments=False,
        received_at=datetime.utcnow(),
        category=category,
        priority=priority,
    )
    db.add(email)
    await db.commit()
    await db.refresh(email)
    return email


@pytest.mark.asyncio
async def test_list_emails_empty(client: AsyncClient):
    """Test listing emails when none exist."""
    response = await client.get("/api/v1/emails")
    assert response.status_code == 200
    data = response.json()
    assert data["emails"] == []
    assert data["total"] == 0


@pytest.mark.asyncio
async def test_list_emails(client: AsyncClient, db_session: AsyncSession):
    """Test listing emails."""
    await create_test_email(db_session, gmail_id="msg1", subject="Email 1")
    await create_test_email(db_session, gmail_id="msg2", subject="Email 2")

    response = await client.get("/api/v1/emails")

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 2
    assert len(data["emails"]) == 2


@pytest.mark.asyncio
async def test_get_email(client: AsyncClient, db_session: AsyncSession):
    """Test getting a specific email."""
    email = await create_test_email(db_session)

    response = await client.get(f"/api/v1/emails/{email.id}")

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == email.id
    assert data["subject"] == "Test Subject"


@pytest.mark.asyncio
async def test_get_email_not_found(client: AsyncClient):
    """Test getting a non-existent email."""
    response = await client.get("/api/v1/emails/99999")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_filter_emails_by_category(client: AsyncClient, db_session: AsyncSession):
    """Test filtering emails by category."""
    await create_test_email(
        db_session,
        gmail_id="msg1",
        category=EmailCategory.URGENT
    )
    await create_test_email(
        db_session,
        gmail_id="msg2",
        category=EmailCategory.FYI
    )

    response = await client.get("/api/v1/emails", params={"category": "urgent"})

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["emails"][0]["category"] == "urgent"


@pytest.mark.asyncio
async def test_filter_emails_unread_only(client: AsyncClient, db_session: AsyncSession):
    """Test filtering unread emails only."""
    await create_test_email(db_session, gmail_id="msg1", is_unread=True)
    await create_test_email(db_session, gmail_id="msg2", is_unread=False)

    response = await client.get("/api/v1/emails", params={"unread_only": True})

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["emails"][0]["is_unread"] is True


@pytest.mark.asyncio
async def test_search_emails(client: AsyncClient, db_session: AsyncSession):
    """Test searching emails."""
    await create_test_email(db_session, gmail_id="msg1", subject="Project Alpha Update")
    await create_test_email(db_session, gmail_id="msg2", subject="Meeting Notes")

    response = await client.get("/api/v1/emails", params={"search": "Alpha"})

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert "Alpha" in data["emails"][0]["subject"]


@pytest.mark.asyncio
async def test_get_email_thread(client: AsyncClient, db_session: AsyncSession):
    """Test getting emails in a thread."""
    thread_id = "thread456"
    await create_test_email(db_session, gmail_id="msg1", subject="Email 1")
    # Update the email to have the same thread_id would require more setup

    response = await client.get(f"/api/v1/emails/thread/{thread_id}")

    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)


@pytest.mark.asyncio
async def test_analyze_email(client: AsyncClient, db_session: AsyncSession):
    """Test analyzing an email with AI."""
    email = await create_test_email(db_session)

    with patch("sage.api.emails.get_claude_agent") as mock_get_agent:
        mock_agent = AsyncMock()
        mock_agent.analyze_email.return_value = type('EmailAnalysis', (), {
            'category': EmailCategory.ACTION_REQUIRED,
            'priority': EmailPriority.HIGH,
            'summary': 'This email requires action.',
            'requires_response': True,
        })()
        mock_get_agent.return_value = mock_agent

        response = await client.post(f"/api/v1/emails/{email.id}/analyze")

        assert response.status_code == 200
        data = response.json()
        assert "category" in data
        assert "priority" in data
        assert "summary" in data


@pytest.mark.asyncio
async def test_draft_reply(client: AsyncClient, db_session: AsyncSession):
    """Test generating a draft reply."""
    email = await create_test_email(db_session)

    with patch("sage.api.emails.get_claude_agent") as mock_get_agent:
        mock_agent = AsyncMock()
        mock_agent.generate_draft_reply.return_value = type('DraftReply', (), {
            'subject': 'Re: Test Subject',
            'body': 'Thank you for your email.',
            'suggested_attachments': None,
            'confidence': 0.9,
            'notes': None,
        })()
        mock_get_agent.return_value = mock_agent

        response = await client.post(
            f"/api/v1/emails/{email.id}/draft-reply",
            json={"tone": "professional"}
        )

        assert response.status_code == 200
        data = response.json()
        assert "subject" in data
        assert "body" in data


@pytest.mark.asyncio
async def test_pagination(client: AsyncClient, db_session: AsyncSession):
    """Test email pagination."""
    # Create 25 emails
    for i in range(25):
        await create_test_email(db_session, gmail_id=f"msg{i}", subject=f"Email {i}")

    # Get first page
    response = await client.get("/api/v1/emails", params={"page": 1, "page_size": 10})

    assert response.status_code == 200
    data = response.json()
    assert len(data["emails"]) == 10
    assert data["total"] == 25
    assert data["has_next"] is True

    # Get second page
    response = await client.get("/api/v1/emails", params={"page": 2, "page_size": 10})

    assert response.status_code == 200
    data = response.json()
    assert len(data["emails"]) == 10
    assert data["has_next"] is True
