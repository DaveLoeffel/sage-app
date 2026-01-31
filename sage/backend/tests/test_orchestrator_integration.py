"""
Integration tests for SageOrchestrator - Phase 4.1

These tests verify the orchestrator flow without requiring a full database.
"""

import pytest
import logging
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

# Configure logging to capture orchestrator activity
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


@pytest.fixture
def mock_data_layer():
    """Create a mock DataLayerService."""
    mock = MagicMock()

    # Mock vector_search to return empty list
    mock.vector_search = AsyncMock(return_value=[])

    # Mock structured_query to return empty list
    mock.structured_query = AsyncMock(return_value=[])

    # Mock store_entity
    mock.store_entity = AsyncMock(return_value="memory_test_123")

    # Mock create_relationship
    mock.create_relationship = AsyncMock(return_value=True)

    return mock


@pytest.fixture
def mock_claude_client():
    """Create a mock Anthropic client."""
    mock = MagicMock()

    # Mock the messages.create method
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text="This is a test response from Claude.")]
    mock.messages.create = AsyncMock(return_value=mock_response)

    return mock


@pytest.mark.asyncio
async def test_orchestrator_initialization(mock_data_layer, mock_claude_client):
    """Test that orchestrator initializes correctly."""
    from sage.agents.orchestrator import SageOrchestrator

    orchestrator = SageOrchestrator(
        data_layer=mock_data_layer,
        claude_client=mock_claude_client
    )

    # Verify agents are initialized
    assert orchestrator.search_agent is not None
    assert orchestrator.indexer_agent is not None
    assert "search" in orchestrator.agents
    assert "indexer" in orchestrator.agents

    logger.info("✓ Orchestrator initialized with search and indexer agents")


@pytest.mark.asyncio
async def test_intent_analysis(mock_data_layer, mock_claude_client):
    """Test intent detection for various query types."""
    from sage.agents.orchestrator import SageOrchestrator

    orchestrator = SageOrchestrator(
        data_layer=mock_data_layer,
        claude_client=mock_claude_client
    )

    test_cases = [
        ("What emails do I have?", "email"),
        ("Show overdue follow-ups", "followup"),
        ("What's on my calendar today?", "meeting"),
        ("Who is John Smith?", "contact"),
        ("What tasks do I have?", "todo"),
        ("Hello, how are you?", "general"),
    ]

    for message, expected_intent in test_cases:
        intent = await orchestrator._analyze_intent(message)
        logger.info(f"Message: '{message}' -> Intent: {intent.primary_intent} (expected: {expected_intent})")
        assert intent.primary_intent == expected_intent, f"Expected {expected_intent}, got {intent.primary_intent}"

    logger.info("✓ All intent detections passed")


@pytest.mark.asyncio
async def test_action_detection(mock_data_layer, mock_claude_client):
    """Test that action keywords are detected."""
    from sage.agents.orchestrator import SageOrchestrator

    orchestrator = SageOrchestrator(
        data_layer=mock_data_layer,
        claude_client=mock_claude_client
    )

    # Queries that should trigger requires_action
    action_queries = [
        "Draft a reply to John",
        "Send an email to the team",
        "Schedule a meeting for tomorrow",
        "Create a reminder for Monday",
    ]

    for message in action_queries:
        intent = await orchestrator._analyze_intent(message)
        logger.info(f"Action query: '{message}' -> requires_action={intent.requires_action}")
        assert intent.requires_action, f"Expected requires_action=True for '{message}'"

    # Queries that should NOT trigger requires_action
    non_action_queries = [
        "What emails do I have?",
        "Show me the calendar",
        "Who is John?",
    ]

    for message in non_action_queries:
        intent = await orchestrator._analyze_intent(message)
        logger.info(f"Non-action query: '{message}' -> requires_action={intent.requires_action}")
        assert not intent.requires_action, f"Expected requires_action=False for '{message}'"

    logger.info("✓ Action detection passed")


@pytest.mark.asyncio
async def test_entity_hint_extraction(mock_data_layer, mock_claude_client):
    """Test that entity hints are extracted from messages."""
    from sage.agents.orchestrator import SageOrchestrator

    orchestrator = SageOrchestrator(
        data_layer=mock_data_layer,
        claude_client=mock_claude_client
    )

    # Test with email address
    intent = await orchestrator._analyze_intent("Show emails from john@example.com")
    logger.info(f"Entity hints for email query: {intent.entity_hints}")
    assert "john@example.com" in intent.entity_hints

    # Test with quoted subject
    intent = await orchestrator._analyze_intent('Find emails about "Project Alpha"')
    logger.info(f"Entity hints for quoted query: {intent.entity_hints}")
    assert "Project Alpha" in intent.entity_hints

    logger.info("✓ Entity hint extraction passed")


@pytest.mark.asyncio
async def test_execution_plan(mock_data_layer, mock_claude_client):
    """Test execution plan generation."""
    from sage.agents.orchestrator import SageOrchestrator

    orchestrator = SageOrchestrator(
        data_layer=mock_data_layer,
        claude_client=mock_claude_client
    )

    intent = await orchestrator._analyze_intent("What emails do I have?")
    plan = await orchestrator._plan_execution("What emails do I have?", intent)

    logger.info(f"Execution plan: intent={plan.intent}, agents={plan.agents_to_invoke}")

    assert plan.intent == "email"
    assert len(plan.agents_to_invoke) > 0
    assert ("search", "search_for_task") in plan.agents_to_invoke

    logger.info("✓ Execution plan generation passed")


@pytest.mark.asyncio
async def test_full_message_processing(mock_data_layer, mock_claude_client):
    """Test complete message processing flow."""
    from sage.agents.orchestrator import SageOrchestrator

    orchestrator = SageOrchestrator(
        data_layer=mock_data_layer,
        claude_client=mock_claude_client
    )
    orchestrator.set_conversation_id("test-conversation-123")

    # Process a message
    response = await orchestrator.process_message("What emails do I have?")

    logger.info(f"Response text: {response.text[:100]}...")
    logger.info(f"Conversation ID: {response.conversation_id}")
    logger.info(f"Agent results count: {len(response.agent_results)}")

    # Verify response
    assert response.text is not None
    assert len(response.text) > 0
    assert response.conversation_id == "test-conversation-123"

    # Verify Claude was called
    mock_claude_client.messages.create.assert_called_once()

    logger.info("✓ Full message processing passed")


@pytest.mark.asyncio
async def test_conversation_history(mock_data_layer, mock_claude_client):
    """Test that conversation history is maintained."""
    from sage.agents.orchestrator import SageOrchestrator

    orchestrator = SageOrchestrator(
        data_layer=mock_data_layer,
        claude_client=mock_claude_client
    )
    orchestrator.set_conversation_id("test-conv")

    # Send first message
    await orchestrator.process_message("Hello")
    assert len(orchestrator.conversation_history) == 2  # user + assistant

    # Reset mock for second call
    mock_claude_client.messages.create.reset_mock()

    # Send second message
    await orchestrator.process_message("What's next?")
    assert len(orchestrator.conversation_history) == 4  # 2 more messages

    # Verify the messages in history have correct roles
    roles = [msg.role for msg in orchestrator.conversation_history]
    assert roles == ["user", "assistant", "user", "assistant"]

    logger.info(f"Conversation history: {len(orchestrator.conversation_history)} messages")
    logger.info("✓ Conversation history tracking passed")


@pytest.mark.asyncio
async def test_feature_flag_routing():
    """Test that feature flag controls routing."""
    from sage.config import get_settings

    settings = get_settings()
    logger.info(f"use_orchestrator flag value: {settings.use_orchestrator}")

    assert hasattr(settings, "use_orchestrator")
    assert isinstance(settings.use_orchestrator, bool)

    logger.info("✓ Feature flag configuration passed")


if __name__ == "__main__":
    import asyncio

    async def run_tests():
        """Run all tests with logging."""
        print("\n" + "="*60)
        print("SageOrchestrator Integration Tests - Phase 4.1")
        print("="*60 + "\n")

        # Create mocks
        mock_dl = MagicMock()
        mock_dl.vector_search = AsyncMock(return_value=[])
        mock_dl.structured_query = AsyncMock(return_value=[])
        mock_dl.store_entity = AsyncMock(return_value="memory_test_123")
        mock_dl.create_relationship = AsyncMock(return_value=True)

        mock_claude = MagicMock()
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="Test response from Claude.")]
        mock_claude.messages.create = AsyncMock(return_value=mock_response)

        # Run tests
        await test_orchestrator_initialization(mock_dl, mock_claude)
        await test_intent_analysis(mock_dl, mock_claude)
        await test_action_detection(mock_dl, mock_claude)
        await test_entity_hint_extraction(mock_dl, mock_claude)
        await test_execution_plan(mock_dl, mock_claude)

        # Reset mock for full flow tests
        mock_claude.messages.create.reset_mock()
        await test_full_message_processing(mock_dl, mock_claude)

        mock_claude.messages.create.reset_mock()
        await test_conversation_history(mock_dl, mock_claude)

        await test_feature_flag_routing()

        print("\n" + "="*60)
        print("All tests passed! ✓")
        print("="*60 + "\n")

    asyncio.run(run_tests())
