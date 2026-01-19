"""Test dashboard endpoints."""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from sage.models.user import User


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


@pytest.mark.asyncio
async def test_dashboard_summary(client: AsyncClient, db_session: AsyncSession):
    """Test dashboard summary endpoint."""
    await create_test_user(db_session)

    response = await client.get("/api/v1/dashboard/summary")

    assert response.status_code == 200
    data = response.json()

    # Check required fields
    assert "followup_summary" in data
    assert "email_summary" in data
    assert "generated_at" in data

    # Check followup summary structure
    assert "total" in data["followup_summary"]
    assert "pending" in data["followup_summary"]
    assert "overdue" in data["followup_summary"]

    # Check email summary structure
    assert "unread_count" in data["email_summary"]


@pytest.mark.asyncio
async def test_dashboard_stats(client: AsyncClient, db_session: AsyncSession):
    """Test dashboard stats endpoint."""
    await create_test_user(db_session)

    response = await client.get("/api/v1/dashboard/stats", params={"days": 7})

    assert response.status_code == 200
    data = response.json()

    assert "period_days" in data
    assert data["period_days"] == 7
    assert "emails_received" in data
    assert "followups_created" in data
