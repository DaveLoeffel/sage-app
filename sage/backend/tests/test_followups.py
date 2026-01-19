"""Test followup endpoints."""

import pytest
from datetime import datetime, timedelta
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from sage.models.user import User
from sage.models.followup import Followup, FollowupStatus, FollowupPriority


async def create_test_user(db: AsyncSession) -> User:
    """Create a test user."""
    user = User(
        email="dave@test.com",
        name="Dave Test",
        timezone="America/New_York",
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def create_test_followup(
    db: AsyncSession,
    user: User,
    status: FollowupStatus = FollowupStatus.PENDING,
    days_offset: int = 2,
) -> Followup:
    """Create a test followup."""
    followup = Followup(
        user_id=user.id,
        gmail_id=f"msg{datetime.utcnow().timestamp()}",
        thread_id="thread123",
        subject="Test Followup",
        contact_email="contact@test.com",
        contact_name="Test Contact",
        status=status,
        priority=FollowupPriority.NORMAL,
        due_date=datetime.utcnow() + timedelta(days=days_offset),
    )
    db.add(followup)
    await db.commit()
    await db.refresh(followup)
    return followup


@pytest.mark.asyncio
async def test_list_followups_empty(client: AsyncClient):
    """Test listing followups when none exist."""
    response = await client.get("/api/v1/followups")
    assert response.status_code == 200
    data = response.json()
    assert data["followups"] == []
    assert data["total"] == 0


@pytest.mark.asyncio
async def test_create_followup(client: AsyncClient, db_session: AsyncSession, sample_followup_data):
    """Test creating a new followup."""
    # First create a user
    user = await create_test_user(db_session)

    response = await client.post(
        "/api/v1/followups",
        json=sample_followup_data
    )

    assert response.status_code == 200
    data = response.json()
    assert data["subject"] == sample_followup_data["subject"]
    assert data["contact_email"] == sample_followup_data["contact_email"]
    assert data["status"] == "pending"


@pytest.mark.asyncio
async def test_get_followup(client: AsyncClient, db_session: AsyncSession):
    """Test getting a specific followup."""
    user = await create_test_user(db_session)
    followup = await create_test_followup(db_session, user)

    response = await client.get(f"/api/v1/followups/{followup.id}")

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == followup.id
    assert data["subject"] == "Test Followup"


@pytest.mark.asyncio
async def test_get_followup_not_found(client: AsyncClient):
    """Test getting a non-existent followup."""
    response = await client.get("/api/v1/followups/99999")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_complete_followup(client: AsyncClient, db_session: AsyncSession):
    """Test completing a followup."""
    user = await create_test_user(db_session)
    followup = await create_test_followup(db_session, user)

    response = await client.post(
        f"/api/v1/followups/{followup.id}/complete",
        params={"reason": "Response received"}
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "completed"
    assert data["completed_reason"] == "Response received"


@pytest.mark.asyncio
async def test_cancel_followup(client: AsyncClient, db_session: AsyncSession):
    """Test cancelling a followup."""
    user = await create_test_user(db_session)
    followup = await create_test_followup(db_session, user)

    response = await client.post(
        f"/api/v1/followups/{followup.id}/cancel",
        params={"reason": "No longer needed"}
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "cancelled"


@pytest.mark.asyncio
async def test_update_followup(client: AsyncClient, db_session: AsyncSession):
    """Test updating a followup."""
    user = await create_test_user(db_session)
    followup = await create_test_followup(db_session, user)

    response = await client.patch(
        f"/api/v1/followups/{followup.id}",
        json={"priority": "high", "notes": "Updated notes"}
    )

    assert response.status_code == 200
    data = response.json()
    assert data["priority"] == "high"
    assert data["notes"] == "Updated notes"


@pytest.mark.asyncio
async def test_get_overdue_followups(client: AsyncClient, db_session: AsyncSession):
    """Test getting overdue followups."""
    user = await create_test_user(db_session)
    # Create an overdue followup (due date in the past)
    await create_test_followup(db_session, user, days_offset=-3)

    response = await client.get("/api/v1/followups/overdue")

    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 1


@pytest.mark.asyncio
async def test_get_due_today_followups(client: AsyncClient, db_session: AsyncSession):
    """Test getting followups due today."""
    user = await create_test_user(db_session)
    # Create a followup due today
    await create_test_followup(db_session, user, days_offset=0)

    response = await client.get("/api/v1/followups/due-today")

    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)


@pytest.mark.asyncio
async def test_delete_followup(client: AsyncClient, db_session: AsyncSession):
    """Test deleting a followup."""
    user = await create_test_user(db_session)
    followup = await create_test_followup(db_session, user)

    response = await client.delete(f"/api/v1/followups/{followup.id}")

    assert response.status_code == 200

    # Verify it's deleted
    response = await client.get(f"/api/v1/followups/{followup.id}")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_filter_followups_by_status(client: AsyncClient, db_session: AsyncSession):
    """Test filtering followups by status."""
    user = await create_test_user(db_session)
    await create_test_followup(db_session, user, status=FollowupStatus.PENDING)
    await create_test_followup(db_session, user, status=FollowupStatus.COMPLETED)

    response = await client.get("/api/v1/followups", params={"status": "pending"})

    assert response.status_code == 200
    data = response.json()
    for followup in data["followups"]:
        assert followup["status"] == "pending"


@pytest.mark.asyncio
async def test_filter_followups_by_priority(client: AsyncClient, db_session: AsyncSession):
    """Test filtering followups by priority."""
    user = await create_test_user(db_session)
    await create_test_followup(db_session, user)

    response = await client.get("/api/v1/followups", params={"priority": "normal"})

    assert response.status_code == 200
