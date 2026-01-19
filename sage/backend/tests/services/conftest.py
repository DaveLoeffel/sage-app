"""
Pytest configuration for service unit tests.

These tests are pure unit tests that don't require database setup.
They test the service classes using mocks.
"""

import pytest


# Override the autouse database fixture from the parent conftest
# to prevent database setup for these unit tests
@pytest.fixture(autouse=True)
async def setup_database():
    """No-op database setup for unit tests."""
    yield
