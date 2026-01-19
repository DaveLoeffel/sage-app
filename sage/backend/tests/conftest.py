"""Pytest configuration and fixtures."""

import asyncio
from typing import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.pool import StaticPool

from sage.services.database import Base, get_db
from sage.main import app


# Create in-memory SQLite for testing
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

engine = create_async_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)

TestSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(autouse=True)
async def setup_database():
    """Create tables before each test."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Get a test database session."""
    async with TestSessionLocal() as session:
        yield session


@pytest.fixture
def override_get_db(db_session: AsyncSession):
    """Override the get_db dependency."""
    async def _override_get_db():
        yield db_session
    return _override_get_db


@pytest.fixture
async def client(override_get_db) -> AsyncGenerator[AsyncClient, None]:
    """Get async test client."""
    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test"
    ) as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest.fixture
def mock_anthropic():
    """Mock the Anthropic client."""
    with patch("sage.core.claude_agent.Anthropic") as mock:
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text='{"message": "Test response"}')]
        mock_client.messages.create.return_value = mock_response
        mock.return_value = mock_client
        yield mock_client


@pytest.fixture
def sample_user_data():
    """Sample user data for tests."""
    return {
        "email": "dave@example.com",
        "name": "Dave Loeffel",
        "timezone": "America/New_York",
    }


@pytest.fixture
def sample_email_data():
    """Sample email data for tests."""
    return {
        "gmail_id": "msg123",
        "thread_id": "thread123",
        "subject": "Test Email Subject",
        "sender_email": "sender@example.com",
        "sender_name": "Test Sender",
        "body_text": "This is a test email body.",
        "snippet": "This is a test...",
        "is_unread": True,
        "has_attachments": False,
    }


@pytest.fixture
def sample_followup_data():
    """Sample followup data for tests."""
    from datetime import datetime, timedelta
    return {
        "gmail_id": "msg123",
        "thread_id": "thread123",
        "subject": "Follow up on project",
        "contact_email": "contact@example.com",
        "contact_name": "Test Contact",
        "priority": "normal",
        "due_date": (datetime.utcnow() + timedelta(days=2)).isoformat(),
    }
