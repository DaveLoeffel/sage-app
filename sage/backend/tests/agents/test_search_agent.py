"""
Unit tests for the SearchAgent.

Tests the SearchAgent's context retrieval and search capabilities
using mock DataLayerInterface implementations.
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

from sage.agents.base import (
    DataLayerInterface,
    IndexedEntity,
    SearchResult,
    Relationship,
    SearchContext,
    AgentType,
)
from sage.agents.foundational.search import SearchAgent


class MockDataLayer(DataLayerInterface):
    """Mock DataLayerInterface for testing."""

    def __init__(self):
        self.entities: dict[str, IndexedEntity] = {}
        self.relationships: list[Relationship] = []
        self.vector_results: list[dict] = []

    def add_entity(self, entity: IndexedEntity) -> None:
        """Add an entity to the mock store."""
        self.entities[entity.id] = entity

    def add_relationship(self, rel: Relationship) -> None:
        """Add a relationship to the mock store."""
        self.relationships.append(rel)

    def set_vector_results(self, results: list[dict]) -> None:
        """Set the results that vector_search will return."""
        self.vector_results = results

    # Write operations (not used by SearchAgent but required by interface)
    async def store_entity(self, entity: IndexedEntity) -> str:
        self.entities[entity.id] = entity
        return entity.id

    async def update_entity(self, entity_id: str, updates: dict) -> bool:
        if entity_id in self.entities:
            entity = self.entities[entity_id]
            if "structured" in updates:
                entity.structured.update(updates["structured"])
            if "analyzed" in updates:
                entity.analyzed.update(updates["analyzed"])
            return True
        return False

    async def delete_entity(self, entity_id: str) -> bool:
        if entity_id in self.entities:
            del self.entities[entity_id]
            return True
        return False

    async def create_relationship(
        self, from_id: str, to_id: str, rel_type: str, metadata: dict | None = None
    ) -> bool:
        self.relationships.append(Relationship(
            from_id=from_id,
            to_id=to_id,
            rel_type=rel_type,
            metadata=metadata or {}
        ))
        return True

    # Read operations (used by SearchAgent)
    async def get_entity(self, entity_id: str) -> IndexedEntity | None:
        return self.entities.get(entity_id)

    async def vector_search(
        self,
        query: str,
        entity_types: list[str] | None = None,
        limit: int = 10
    ) -> list[SearchResult]:
        results = []
        for item in self.vector_results[:limit]:
            entity_id = item.get("entity_id")
            if entity_id and entity_id in self.entities:
                entity = self.entities[entity_id]
                # Filter by entity type if specified
                if entity_types is None or entity.entity_type in entity_types:
                    results.append(SearchResult(
                        entity=entity,
                        score=item.get("score", 0.8),
                        match_type="semantic"
                    ))
        return results

    async def structured_query(
        self,
        filters: dict,
        entity_type: str,
        limit: int = 100
    ) -> list[IndexedEntity]:
        results = []
        for entity in self.entities.values():
            if entity.entity_type != entity_type:
                continue

            # Check filters
            matches = True
            for key, value in filters.items():
                if key == "date_range":
                    # Skip date range filtering in mock
                    continue
                entity_value = entity.structured.get(key)
                if isinstance(value, list):
                    if entity_value not in value:
                        matches = False
                elif entity_value != value:
                    matches = False

            if matches:
                results.append(entity)
                if len(results) >= limit:
                    break

        return results

    async def get_relationships(
        self,
        entity_id: str,
        rel_types: list[str] | None = None
    ) -> list[Relationship]:
        results = []
        for rel in self.relationships:
            if rel.from_id == entity_id or rel.to_id == entity_id:
                if rel_types is None or rel.rel_type in rel_types:
                    results.append(rel)
        return results


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def mock_data_layer() -> MockDataLayer:
    """Create a mock data layer with some test data."""
    dl = MockDataLayer()

    # Add some test emails
    dl.add_entity(IndexedEntity(
        id="email_123",
        entity_type="email",
        source="gmail",
        structured={
            "subject": "Q4 Budget Review",
            "sender_email": "john@example.com",
            "sender_name": "John Smith",
            "thread_id": "thread_abc",
            "is_unread": True,
            "received_at": "2026-01-15T10:00:00",
        },
        analyzed={
            "priority": "high",
            "category": "action_required",
            "summary": "Review needed for Q4 budget",
        }
    ))

    dl.add_entity(IndexedEntity(
        id="email_456",
        entity_type="email",
        source="gmail",
        structured={
            "subject": "Meeting Notes - Project Alpha",
            "sender_email": "jane@example.com",
            "sender_name": "Jane Doe",
            "thread_id": "thread_def",
            "is_unread": False,
            "received_at": "2026-01-14T14:00:00",
        },
        analyzed={
            "priority": "normal",
            "category": "fyi",
            "summary": "Notes from project meeting",
        }
    ))

    # Add a contact
    dl.add_entity(IndexedEntity(
        id="contact_john",
        entity_type="contact",
        source="gmail",
        structured={
            "email": "john@example.com",
            "name": "John Smith",
            "company": "Acme Corp",
        }
    ))

    # Add a follow-up
    dl.add_entity(IndexedEntity(
        id="followup_1",
        entity_type="followup",
        source="sage",
        structured={
            "subject": "Follow up on Q4 Budget",
            "contact_email": "john@example.com",
            "status": "pending",
            "due_date": "2026-01-20",
            "thread_id": "thread_abc",
        }
    ))

    # Add a meeting
    dl.add_entity(IndexedEntity(
        id="meeting_1",
        entity_type="meeting",
        source="fireflies",
        structured={
            "title": "Project Alpha Kickoff",
            "date": "2026-01-10T09:00:00",
            "participants": ["john@example.com", "jane@example.com"],
        },
        analyzed={
            "summary": "Initial project planning meeting",
        }
    ))

    # Add relationships
    dl.add_relationship(Relationship(
        from_id="email_123",
        to_id="contact_john",
        rel_type="sent_by",
        metadata={}
    ))

    dl.add_relationship(Relationship(
        from_id="followup_1",
        to_id="email_123",
        rel_type="created_from",
        metadata={}
    ))

    return dl


@pytest.fixture
def search_agent(mock_data_layer: MockDataLayer) -> SearchAgent:
    """Create a SearchAgent with mock data layer."""
    return SearchAgent(data_layer=mock_data_layer)


# =============================================================================
# Test SearchAgent Properties
# =============================================================================

class TestSearchAgentProperties:
    """Test SearchAgent class properties."""

    def test_name(self, search_agent: SearchAgent):
        assert search_agent.name == "search"

    def test_description(self, search_agent: SearchAgent):
        assert "retrieves" in search_agent.description.lower()

    def test_agent_type(self, search_agent: SearchAgent):
        assert search_agent.agent_type == AgentType.FOUNDATIONAL

    def test_capabilities(self, search_agent: SearchAgent):
        expected = [
            "search_for_task",
            "semantic_search",
            "entity_lookup",
            "relationship_traverse",
            "temporal_search",
            "get_relevant_memories",
        ]
        assert search_agent.capabilities == expected

    def test_supports_capability(self, search_agent: SearchAgent):
        assert search_agent.supports_capability("semantic_search")
        assert not search_agent.supports_capability("invalid_capability")


# =============================================================================
# Test Execute Method
# =============================================================================

class TestExecute:
    """Test the execute() method dispatcher."""

    @pytest.mark.asyncio
    async def test_execute_semantic_search(
        self, search_agent: SearchAgent, mock_data_layer: MockDataLayer
    ):
        # Set up vector results
        mock_data_layer.set_vector_results([
            {"entity_id": "email_123", "score": 0.9}
        ])

        result = await search_agent.execute(
            capability="semantic_search",
            params={"query": "budget review", "limit": 5}
        )

        assert result.success
        assert "results" in result.data

    @pytest.mark.asyncio
    async def test_execute_entity_lookup(self, search_agent: SearchAgent):
        result = await search_agent.execute(
            capability="entity_lookup",
            params={"entity_id": "email_123"}
        )

        assert result.success
        assert result.data["entity"] is not None
        assert result.data["entity"]["id"] == "email_123"

    @pytest.mark.asyncio
    async def test_execute_invalid_capability(self, search_agent: SearchAgent):
        with pytest.raises(ValueError):
            await search_agent.execute(
                capability="invalid_capability",
                params={}
            )

    @pytest.mark.asyncio
    async def test_execute_handles_errors(self, search_agent: SearchAgent):
        # Pass invalid params to trigger an error
        result = await search_agent.execute(
            capability="temporal_search",
            params={"start_time": "invalid", "end_time": "also_invalid"}
        )

        assert not result.success
        assert len(result.errors) > 0


# =============================================================================
# Test search_for_task
# =============================================================================

class TestSearchForTask:
    """Test the search_for_task method."""

    @pytest.mark.asyncio
    async def test_builds_context_for_email_agent(
        self, search_agent: SearchAgent, mock_data_layer: MockDataLayer
    ):
        mock_data_layer.set_vector_results([
            {"entity_id": "email_123", "score": 0.9}
        ])

        context = await search_agent.search_for_task(
            requesting_agent="email",
            task_description="Find emails about budget",
            max_results=10
        )

        assert isinstance(context, SearchContext)
        assert context.retrieval_metadata["requesting_agent"] == "email"
        assert "entities_retrieved" in context.retrieval_metadata

    @pytest.mark.asyncio
    async def test_enriches_for_followup_agent(
        self, search_agent: SearchAgent, mock_data_layer: MockDataLayer
    ):
        context = await search_agent.search_for_task(
            requesting_agent="followup",
            task_description="Check overdue follow-ups",
            max_results=10
        )

        # Should include the pending follow-up
        assert len(context.relevant_followups) > 0

    @pytest.mark.asyncio
    async def test_enriches_for_briefing_agent(
        self, search_agent: SearchAgent, mock_data_layer: MockDataLayer
    ):
        context = await search_agent.search_for_task(
            requesting_agent="briefing",
            task_description="Generate morning briefing",
            max_results=10
        )

        # Should include high-priority emails and follow-ups
        assert isinstance(context.relevant_emails, list)
        assert isinstance(context.relevant_followups, list)

    @pytest.mark.asyncio
    async def test_uses_entity_hints(
        self, search_agent: SearchAgent, mock_data_layer: MockDataLayer
    ):
        context = await search_agent.search_for_task(
            requesting_agent="email",
            task_description="Analyze email",
            entity_hints=["email_123"],
            max_results=10
        )

        # Should include the hinted entity
        email_ids = [e["id"] for e in context.relevant_emails]
        assert "email_123" in email_ids

    @pytest.mark.asyncio
    async def test_includes_temporal_summary(
        self, search_agent: SearchAgent, mock_data_layer: MockDataLayer
    ):
        mock_data_layer.set_vector_results([
            {"entity_id": "email_123", "score": 0.9}
        ])

        context = await search_agent.search_for_task(
            requesting_agent="email",
            task_description="Find emails",
            max_results=10
        )

        assert context.temporal_summary
        assert "Context includes" in context.temporal_summary


# =============================================================================
# Test semantic_search
# =============================================================================

class TestSemanticSearch:
    """Test the semantic_search method."""

    @pytest.mark.asyncio
    async def test_returns_search_results(
        self, search_agent: SearchAgent, mock_data_layer: MockDataLayer
    ):
        mock_data_layer.set_vector_results([
            {"entity_id": "email_123", "score": 0.9},
            {"entity_id": "email_456", "score": 0.7}
        ])

        results = await search_agent.semantic_search(
            query="budget review",
            limit=10
        )

        assert len(results) == 2
        assert all(isinstance(r, SearchResult) for r in results)

    @pytest.mark.asyncio
    async def test_filters_by_score_threshold(
        self, search_agent: SearchAgent, mock_data_layer: MockDataLayer
    ):
        mock_data_layer.set_vector_results([
            {"entity_id": "email_123", "score": 0.9},
            {"entity_id": "email_456", "score": 0.2}  # Below threshold
        ])

        results = await search_agent.semantic_search(
            query="budget",
            limit=10,
            score_threshold=0.5
        )

        assert len(results) == 1
        assert results[0].score >= 0.5

    @pytest.mark.asyncio
    async def test_filters_by_entity_type(
        self, search_agent: SearchAgent, mock_data_layer: MockDataLayer
    ):
        mock_data_layer.set_vector_results([
            {"entity_id": "email_123", "score": 0.9},
            {"entity_id": "contact_john", "score": 0.8}
        ])

        results = await search_agent.semantic_search(
            query="john",
            entity_types=["email"],
            limit=10
        )

        assert all(r.entity.entity_type == "email" for r in results)


# =============================================================================
# Test entity_lookup
# =============================================================================

class TestEntityLookup:
    """Test the entity_lookup method."""

    @pytest.mark.asyncio
    async def test_lookup_by_id(self, search_agent: SearchAgent):
        result = await search_agent.entity_lookup(entity_id="email_123")

        assert result is not None
        assert result["id"] == "email_123"
        assert result["subject"] == "Q4 Budget Review"

    @pytest.mark.asyncio
    async def test_lookup_not_found(self, search_agent: SearchAgent):
        result = await search_agent.entity_lookup(entity_id="nonexistent")

        assert result is None

    @pytest.mark.asyncio
    async def test_lookup_by_filters(self, search_agent: SearchAgent):
        results = await search_agent.entity_lookup(
            entity_type="email",
            filters={"is_unread": True}
        )

        assert isinstance(results, list)
        assert len(results) == 1
        assert results[0]["is_unread"] is True


# =============================================================================
# Test relationship_traverse
# =============================================================================

class TestRelationshipTraverse:
    """Test the relationship_traverse method."""

    @pytest.mark.asyncio
    async def test_finds_related_entities(self, search_agent: SearchAgent):
        related = await search_agent.relationship_traverse(
            entity_id="email_123"
        )

        assert len(related) > 0
        # Should find the contact
        contact_ids = [e["id"] for e in related]
        assert "contact_john" in contact_ids

    @pytest.mark.asyncio
    async def test_includes_relationship_info(self, search_agent: SearchAgent):
        related = await search_agent.relationship_traverse(
            entity_id="email_123"
        )

        for entity in related:
            assert "relationship" in entity
            assert "type" in entity["relationship"]
            assert "direction" in entity["relationship"]

    @pytest.mark.asyncio
    async def test_filters_by_relationship_type(self, search_agent: SearchAgent):
        related = await search_agent.relationship_traverse(
            entity_id="email_123",
            rel_types=["sent_by"]
        )

        for entity in related:
            assert entity["relationship"]["type"] == "sent_by"


# =============================================================================
# Test temporal_search
# =============================================================================

class TestTemporalSearch:
    """Test the temporal_search method."""

    @pytest.mark.asyncio
    async def test_accepts_string_times(self, search_agent: SearchAgent):
        results = await search_agent.temporal_search(
            start_time="2026-01-01T00:00:00",
            end_time="2026-01-31T23:59:59",
            entity_types=["email"]
        )

        assert isinstance(results, list)

    @pytest.mark.asyncio
    async def test_accepts_datetime_objects(self, search_agent: SearchAgent):
        results = await search_agent.temporal_search(
            start_time=datetime(2026, 1, 1),
            end_time=datetime(2026, 1, 31),
            entity_types=["email"]
        )

        assert isinstance(results, list)


# =============================================================================
# Test get_relevant_memories
# =============================================================================

class TestGetRelevantMemories:
    """Test the get_relevant_memories method."""

    @pytest.mark.asyncio
    async def test_returns_search_context(self, search_agent: SearchAgent):
        context = await search_agent.get_relevant_memories(
            query="budget discussion"
        )

        assert isinstance(context, SearchContext)
        assert "query" in context.retrieval_metadata

    @pytest.mark.asyncio
    async def test_includes_conversation_id_in_metadata(
        self, search_agent: SearchAgent
    ):
        context = await search_agent.get_relevant_memories(
            query="budget",
            conversation_id="conv_123"
        )

        assert context.retrieval_metadata["conversation_id"] == "conv_123"


# =============================================================================
# Test get_contact_context
# =============================================================================

class TestGetContactContext:
    """Test the get_contact_context method."""

    @pytest.mark.asyncio
    async def test_returns_contact_info(self, search_agent: SearchAgent):
        result = await search_agent.get_contact_context(
            email="john@example.com"
        )

        assert result["contact"] is not None
        assert result["contact"]["email"] == "john@example.com"

    @pytest.mark.asyncio
    async def test_includes_emails_from_contact(self, search_agent: SearchAgent):
        result = await search_agent.get_contact_context(
            email="john@example.com"
        )

        assert len(result["recent_emails"]) > 0

    @pytest.mark.asyncio
    async def test_calculates_total_interactions(self, search_agent: SearchAgent):
        result = await search_agent.get_contact_context(
            email="john@example.com"
        )

        expected_total = (
            len(result["recent_emails"]) +
            len(result["meetings"]) +
            len(result["followups"])
        )
        assert result["total_interactions"] == expected_total

    @pytest.mark.asyncio
    async def test_handles_unknown_contact(self, search_agent: SearchAgent):
        result = await search_agent.get_contact_context(
            email="unknown@example.com"
        )

        assert result["contact"] is None
        assert result["total_interactions"] == 0


# =============================================================================
# Test get_thread_context
# =============================================================================

class TestGetThreadContext:
    """Test the get_thread_context method."""

    @pytest.mark.asyncio
    async def test_returns_thread_emails(self, search_agent: SearchAgent):
        result = await search_agent.get_thread_context(
            thread_id="thread_abc"
        )

        assert result["thread_id"] == "thread_abc"
        assert len(result["emails"]) > 0

    @pytest.mark.asyncio
    async def test_includes_participants(self, search_agent: SearchAgent):
        result = await search_agent.get_thread_context(
            thread_id="thread_abc"
        )

        assert len(result["participants"]) > 0

    @pytest.mark.asyncio
    async def test_includes_followups(self, search_agent: SearchAgent):
        result = await search_agent.get_thread_context(
            thread_id="thread_abc"
        )

        # Thread abc has a related follow-up
        assert len(result["followups"]) > 0

    @pytest.mark.asyncio
    async def test_generates_summary(self, search_agent: SearchAgent):
        result = await search_agent.get_thread_context(
            thread_id="thread_abc"
        )

        assert result["summary"]
        assert "Thread with" in result["summary"]

    @pytest.mark.asyncio
    async def test_handles_empty_thread(self, search_agent: SearchAgent):
        result = await search_agent.get_thread_context(
            thread_id="nonexistent_thread"
        )

        assert result["emails"] == []
        assert result["summary"] == ""
