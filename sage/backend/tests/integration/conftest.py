"""
Pytest configuration for integration tests.

These tests use mock data layers and don't need real database setup.
Override the autouse setup_database fixture from parent conftest.
"""

import pytest


@pytest.fixture(autouse=True)
async def setup_database():
    """Override parent fixture - integration tests use mock data layers."""
    # No-op: integration tests don't need real database
    yield
