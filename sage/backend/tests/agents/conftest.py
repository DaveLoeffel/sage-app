"""
Pytest configuration for agent unit tests.

These tests are pure unit tests that don't require database or API setup.
They test the agent base classes and abstractions in isolation.
"""

import pytest


# Override the autouse database fixture from the parent conftest
# to prevent database setup for these unit tests
@pytest.fixture(autouse=True)
async def setup_database():
    """No-op database setup for unit tests."""
    yield
