"""
Unit tests for agent base classes.

Tests the core abstractions in sage/agents/base.py:
- AgentResult dataclass
- SearchContext dataclass
- IndexedEntity, SearchResult, Relationship dataclasses
- DataLayerInterface abstract class
- BaseAgent abstract class

These are unit tests that don't require database or API setup.
"""

import pytest
from typing import Any
from unittest.mock import AsyncMock, MagicMock

from sage.agents.base import (
    AgentType,
    AgentResult,
    SearchContext,
    IndexedEntity,
    SearchResult,
    Relationship,
    DataLayerInterface,
    BaseAgent,
)


# =============================================================================
# AgentResult Tests
# =============================================================================

class TestAgentResult:
    """Tests for the AgentResult dataclass."""

    def test_create_success_result(self):
        """Test creating a successful result."""
        result = AgentResult(
            success=True,
            data={"message": "Task completed"}
        )
        assert result.success is True
        assert result.data == {"message": "Task completed"}
        assert result.errors == []
        assert result.warnings == []
        assert result.confidence == 1.0
        assert result.entities_to_index == []
        assert result.requires_approval is False
        assert result.approval_context is None

    def test_create_failure_result(self):
        """Test creating a failure result with errors."""
        result = AgentResult(
            success=False,
            data={},
            errors=["Something went wrong", "Another error"]
        )
        assert result.success is False
        assert result.errors == ["Something went wrong", "Another error"]

    def test_result_with_warnings(self):
        """Test result with warnings."""
        result = AgentResult(
            success=True,
            data={"partial": True},
            warnings=["Some data was unavailable"]
        )
        assert result.success is True
        assert result.warnings == ["Some data was unavailable"]

    def test_result_with_confidence(self):
        """Test result with confidence score."""
        result = AgentResult(
            success=True,
            data={"prediction": "high priority"},
            confidence=0.85
        )
        assert result.confidence == 0.85

    def test_result_with_entities_to_index(self):
        """Test result with entities that should be indexed."""
        entities = [
            {"entity_type": "memory", "content": "User prefers morning emails"},
            {"entity_type": "fact", "content": "Meeting moved to Friday"},
        ]
        result = AgentResult(
            success=True,
            data={},
            entities_to_index=entities
        )
        assert len(result.entities_to_index) == 2
        assert result.entities_to_index[0]["entity_type"] == "memory"

    def test_result_requiring_approval(self):
        """Test result that requires human approval."""
        result = AgentResult(
            success=True,
            data={"draft_email": "Dear John..."},
            requires_approval=True,
            approval_context="Send email to john@example.com"
        )
        assert result.requires_approval is True
        assert result.approval_context == "Send email to john@example.com"

    def test_result_none_lists_become_empty(self):
        """Test that None lists are converted to empty lists in __post_init__."""
        result = AgentResult(
            success=True,
            data={},
            errors=None,
            warnings=None,
            entities_to_index=None
        )
        assert result.errors == []
        assert result.warnings == []
        assert result.entities_to_index == []


# =============================================================================
# SearchContext Tests
# =============================================================================

class TestSearchContext:
    """Tests for the SearchContext dataclass."""

    def test_create_empty_context(self):
        """Test creating an empty search context."""
        ctx = SearchContext()
        assert ctx.relevant_emails == []
        assert ctx.relevant_contacts == []
        assert ctx.relevant_followups == []
        assert ctx.relevant_meetings == []
        assert ctx.relevant_events == []
        assert ctx.relevant_memories == []
        assert ctx.relationship_graph == {}
        assert ctx.temporal_summary == ""
        assert ctx.total_tokens == 0
        assert ctx.retrieval_metadata == {}

    def test_context_is_empty(self):
        """Test is_empty() returns True for empty context."""
        ctx = SearchContext()
        assert ctx.is_empty() is True

    def test_context_with_emails_not_empty(self):
        """Test is_empty() returns False when emails present."""
        ctx = SearchContext(
            relevant_emails=[{"id": "email_123", "subject": "Test"}]
        )
        assert ctx.is_empty() is False

    def test_context_with_contacts_not_empty(self):
        """Test is_empty() returns False when contacts present."""
        ctx = SearchContext(
            relevant_contacts=[{"id": "contact_123", "name": "John"}]
        )
        assert ctx.is_empty() is False

    def test_context_with_memories_not_empty(self):
        """Test is_empty() returns False when memories present."""
        ctx = SearchContext(
            relevant_memories=[{"id": "mem_123", "fact": "User preference"}]
        )
        assert ctx.is_empty() is False

    def test_context_with_all_data(self):
        """Test context with all types of data."""
        ctx = SearchContext(
            relevant_emails=[{"id": "email_1"}],
            relevant_contacts=[{"id": "contact_1"}],
            relevant_followups=[{"id": "followup_1"}],
            relevant_meetings=[{"id": "meeting_1"}],
            relevant_events=[{"id": "event_1"}],
            relevant_memories=[{"id": "memory_1"}],
            relationship_graph={"contact_1": ["email_1"]},
            temporal_summary="Last 7 days of activity",
            total_tokens=1500,
            retrieval_metadata={"query": "test", "took_ms": 45}
        )
        assert ctx.is_empty() is False
        assert ctx.total_tokens == 1500
        assert "query" in ctx.retrieval_metadata


# =============================================================================
# IndexedEntity Tests
# =============================================================================

class TestIndexedEntity:
    """Tests for the IndexedEntity dataclass."""

    def test_create_minimal_entity(self):
        """Test creating entity with required fields only."""
        entity = IndexedEntity(
            id="email_123",
            entity_type="email",
            source="gmail"
        )
        assert entity.id == "email_123"
        assert entity.entity_type == "email"
        assert entity.source == "gmail"
        assert entity.structured == {}
        assert entity.analyzed == {}
        assert entity.relationships == {}
        assert entity.embeddings == {}
        assert entity.metadata == {}

    def test_create_full_entity(self):
        """Test creating entity with all fields."""
        entity = IndexedEntity(
            id="email_123",
            entity_type="email",
            source="gmail",
            structured={
                "subject": "Q4 Report",
                "from_email": "laura@example.com"
            },
            analyzed={
                "priority": "high",
                "sentiment": "neutral"
            },
            relationships={
                "contact_id": "contact_laura",
                "thread_emails": ["email_122"]
            },
            embeddings={
                "qdrant_id": "vec_123",
                "model": "all-MiniLM-L6-v2"
            },
            metadata={
                "indexed_at": "2026-01-18T10:00:00Z"
            }
        )
        assert entity.structured["subject"] == "Q4 Report"
        assert entity.analyzed["priority"] == "high"
        assert entity.relationships["contact_id"] == "contact_laura"
        assert entity.embeddings["model"] == "all-MiniLM-L6-v2"


# =============================================================================
# SearchResult Tests
# =============================================================================

class TestSearchResult:
    """Tests for the SearchResult dataclass."""

    def test_create_search_result(self):
        """Test creating a search result."""
        entity = IndexedEntity(
            id="email_123",
            entity_type="email",
            source="gmail"
        )
        result = SearchResult(
            entity=entity,
            score=0.92,
            match_type="semantic"
        )
        assert result.entity.id == "email_123"
        assert result.score == 0.92
        assert result.match_type == "semantic"

    def test_search_result_match_types(self):
        """Test different match types."""
        entity = IndexedEntity(id="e1", entity_type="email", source="gmail")

        semantic = SearchResult(entity=entity, score=0.9, match_type="semantic")
        keyword = SearchResult(entity=entity, score=0.85, match_type="keyword")
        structured = SearchResult(entity=entity, score=1.0, match_type="structured")

        assert semantic.match_type == "semantic"
        assert keyword.match_type == "keyword"
        assert structured.match_type == "structured"


# =============================================================================
# Relationship Tests
# =============================================================================

class TestRelationship:
    """Tests for the Relationship dataclass."""

    def test_create_relationship(self):
        """Test creating a relationship."""
        rel = Relationship(
            from_id="email_123",
            to_id="contact_456",
            rel_type="sent_by"
        )
        assert rel.from_id == "email_123"
        assert rel.to_id == "contact_456"
        assert rel.rel_type == "sent_by"
        assert rel.metadata == {}

    def test_relationship_with_metadata(self):
        """Test relationship with metadata."""
        rel = Relationship(
            from_id="fact_old",
            to_id="fact_new",
            rel_type="superseded_by",
            metadata={
                "reason": "Updated information from user",
                "superseded_at": "2026-01-18T10:00:00Z"
            }
        )
        assert rel.rel_type == "superseded_by"
        assert rel.metadata["reason"] == "Updated information from user"


# =============================================================================
# DataLayerInterface Tests
# =============================================================================

class ConcreteDataLayer(DataLayerInterface):
    """Concrete implementation for testing."""

    def __init__(self):
        self.entities = {}
        self.relationships = []

    async def store_entity(self, entity: IndexedEntity) -> str:
        self.entities[entity.id] = entity
        return entity.id

    async def update_entity(self, entity_id: str, updates: dict) -> bool:
        if entity_id in self.entities:
            for key, value in updates.items():
                setattr(self.entities[entity_id], key, value)
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
        self.relationships.append(Relationship(from_id, to_id, rel_type, metadata or {}))
        return True

    async def get_entity(self, entity_id: str) -> IndexedEntity | None:
        return self.entities.get(entity_id)

    async def vector_search(
        self, query: str, entity_types: list[str] | None = None, limit: int = 10
    ) -> list[SearchResult]:
        # Simple mock: return all entities as results
        results = []
        for entity in list(self.entities.values())[:limit]:
            if entity_types is None or entity.entity_type in entity_types:
                results.append(SearchResult(entity=entity, score=0.8, match_type="semantic"))
        return results

    async def structured_query(
        self, filters: dict, entity_type: str, limit: int = 100
    ) -> list[IndexedEntity]:
        return [e for e in self.entities.values() if e.entity_type == entity_type][:limit]

    async def get_relationships(
        self, entity_id: str, rel_types: list[str] | None = None
    ) -> list[Relationship]:
        results = [r for r in self.relationships if r.from_id == entity_id]
        if rel_types:
            results = [r for r in results if r.rel_type in rel_types]
        return results


class TestDataLayerInterface:
    """Tests for DataLayerInterface concrete implementation."""

    @pytest.fixture
    def data_layer(self):
        """Create a concrete data layer for testing."""
        return ConcreteDataLayer()

    @pytest.mark.asyncio
    async def test_store_and_retrieve_entity(self, data_layer):
        """Test storing and retrieving an entity."""
        entity = IndexedEntity(
            id="test_123",
            entity_type="email",
            source="gmail",
            structured={"subject": "Test"}
        )

        entity_id = await data_layer.store_entity(entity)
        assert entity_id == "test_123"

        retrieved = await data_layer.get_entity("test_123")
        assert retrieved is not None
        assert retrieved.structured["subject"] == "Test"

    @pytest.mark.asyncio
    async def test_update_entity(self, data_layer):
        """Test updating an entity."""
        entity = IndexedEntity(id="test_123", entity_type="email", source="gmail")
        await data_layer.store_entity(entity)

        success = await data_layer.update_entity("test_123", {"source": "manual"})
        assert success is True

        retrieved = await data_layer.get_entity("test_123")
        assert retrieved.source == "manual"

    @pytest.mark.asyncio
    async def test_delete_entity(self, data_layer):
        """Test deleting an entity."""
        entity = IndexedEntity(id="test_123", entity_type="email", source="gmail")
        await data_layer.store_entity(entity)

        success = await data_layer.delete_entity("test_123")
        assert success is True

        retrieved = await data_layer.get_entity("test_123")
        assert retrieved is None

    @pytest.mark.asyncio
    async def test_create_relationship(self, data_layer):
        """Test creating a relationship."""
        success = await data_layer.create_relationship(
            from_id="email_1",
            to_id="contact_1",
            rel_type="sent_by"
        )
        assert success is True

        rels = await data_layer.get_relationships("email_1")
        assert len(rels) == 1
        assert rels[0].to_id == "contact_1"

    @pytest.mark.asyncio
    async def test_vector_search(self, data_layer):
        """Test vector search."""
        for i in range(3):
            entity = IndexedEntity(id=f"email_{i}", entity_type="email", source="gmail")
            await data_layer.store_entity(entity)

        results = await data_layer.vector_search("test query", limit=2)
        assert len(results) == 2
        assert all(r.match_type == "semantic" for r in results)

    @pytest.mark.asyncio
    async def test_structured_query(self, data_layer):
        """Test structured query."""
        email = IndexedEntity(id="email_1", entity_type="email", source="gmail")
        contact = IndexedEntity(id="contact_1", entity_type="contact", source="manual")
        await data_layer.store_entity(email)
        await data_layer.store_entity(contact)

        results = await data_layer.structured_query(filters={}, entity_type="email")
        assert len(results) == 1
        assert results[0].entity_type == "email"


# =============================================================================
# BaseAgent Tests
# =============================================================================

class ConcreteAgent(BaseAgent):
    """Concrete agent implementation for testing."""

    name = "test_agent"
    description = "A test agent for unit testing"
    capabilities = ["capability_one", "capability_two", "capability_three"]
    agent_type = AgentType.TASK

    async def execute(
        self,
        capability: str,
        params: dict[str, Any],
        context: SearchContext | None = None
    ) -> AgentResult:
        self._validate_capability(capability)

        if capability == "capability_one":
            return AgentResult(success=True, data={"result": "one"})
        elif capability == "capability_two":
            return AgentResult(success=True, data={"result": "two"})
        elif capability == "capability_three":
            # Simulates needing context
            if context is None:
                context = await self.get_context("test task")
            return AgentResult(
                success=True,
                data={"result": "three", "had_context": not context.is_empty()}
            )
        return AgentResult(success=False, data={}, errors=["Unknown"])


class TestBaseAgent:
    """Tests for BaseAgent abstract class."""

    @pytest.fixture
    def mock_search_agent(self):
        """Create a mock search agent."""
        mock = AsyncMock()
        mock.search_for_task = AsyncMock(return_value=SearchContext(
            relevant_emails=[{"id": "email_1"}]
        ))
        return mock

    @pytest.fixture
    def mock_indexer_agent(self):
        """Create a mock indexer agent."""
        mock = AsyncMock()
        mock.index_entity = AsyncMock(return_value="indexed_123")
        return mock

    @pytest.fixture
    def agent(self, mock_search_agent, mock_indexer_agent):
        """Create a concrete agent for testing."""
        return ConcreteAgent(
            search_agent=mock_search_agent,
            indexer_agent=mock_indexer_agent
        )

    def test_agent_properties(self, agent):
        """Test agent has required properties."""
        assert agent.name == "test_agent"
        assert agent.description == "A test agent for unit testing"
        assert "capability_one" in agent.capabilities
        assert agent.agent_type == AgentType.TASK

    def test_supports_capability(self, agent):
        """Test supports_capability method."""
        assert agent.supports_capability("capability_one") is True
        assert agent.supports_capability("capability_two") is True
        assert agent.supports_capability("nonexistent") is False

    def test_validate_capability_raises_on_invalid(self, agent):
        """Test _validate_capability raises ValueError for invalid capability."""
        with pytest.raises(ValueError) as exc_info:
            agent._validate_capability("invalid_capability")

        assert "invalid_capability" in str(exc_info.value)
        assert "test_agent" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_execute_capability_one(self, agent):
        """Test executing capability_one."""
        result = await agent.execute("capability_one", {})
        assert result.success is True
        assert result.data["result"] == "one"

    @pytest.mark.asyncio
    async def test_execute_capability_two(self, agent):
        """Test executing capability_two."""
        result = await agent.execute("capability_two", {})
        assert result.success is True
        assert result.data["result"] == "two"

    @pytest.mark.asyncio
    async def test_execute_invalid_capability_raises(self, agent):
        """Test executing invalid capability raises ValueError."""
        with pytest.raises(ValueError):
            await agent.execute("invalid", {})

    @pytest.mark.asyncio
    async def test_get_context_calls_search_agent(self, agent, mock_search_agent):
        """Test get_context calls search agent."""
        context = await agent.get_context("find relevant emails")

        mock_search_agent.search_for_task.assert_called_once_with(
            requesting_agent="test_agent",
            task_description="find relevant emails",
            entity_hints=None
        )
        assert not context.is_empty()

    @pytest.mark.asyncio
    async def test_get_context_with_hints(self, agent, mock_search_agent):
        """Test get_context passes hints to search agent."""
        await agent.get_context("find emails", hints=["email_123", "contact_456"])

        mock_search_agent.search_for_task.assert_called_once_with(
            requesting_agent="test_agent",
            task_description="find emails",
            entity_hints=["email_123", "contact_456"]
        )

    @pytest.mark.asyncio
    async def test_get_context_without_search_agent(self):
        """Test get_context returns empty context when no search agent."""
        agent = ConcreteAgent(search_agent=None, indexer_agent=None)
        context = await agent.get_context("test")
        assert context.is_empty()

    @pytest.mark.asyncio
    async def test_persist_data_calls_indexer(self, agent, mock_indexer_agent):
        """Test persist_data calls indexer agent."""
        entities = [
            {"entity_type": "memory", "content": "fact 1"},
            {"entity_type": "fact", "content": "fact 2"},
        ]

        indexed_ids = await agent.persist_data(entities)

        assert len(indexed_ids) == 2
        assert mock_indexer_agent.index_entity.call_count == 2

    @pytest.mark.asyncio
    async def test_persist_data_without_indexer(self):
        """Test persist_data returns empty list when no indexer agent."""
        agent = ConcreteAgent(search_agent=None, indexer_agent=None)
        indexed_ids = await agent.persist_data([{"entity_type": "test"}])
        assert indexed_ids == []

    @pytest.mark.asyncio
    async def test_execute_with_provided_context(self, agent):
        """Test execute uses provided context."""
        provided_context = SearchContext(
            relevant_emails=[{"id": "provided_email"}]
        )
        result = await agent.execute(
            "capability_three",
            {},
            context=provided_context
        )
        assert result.success is True
        assert result.data["had_context"] is True

    @pytest.mark.asyncio
    async def test_execute_fetches_context_if_not_provided(self, agent, mock_search_agent):
        """Test execute fetches context from search agent if not provided."""
        result = await agent.execute("capability_three", {})

        assert result.success is True
        assert result.data["had_context"] is True
        mock_search_agent.search_for_task.assert_called()


# =============================================================================
# AgentType Tests
# =============================================================================

class TestAgentType:
    """Tests for the AgentType enum."""

    def test_agent_types_exist(self):
        """Test all agent types are defined."""
        assert AgentType.FOUNDATIONAL.value == "foundational"
        assert AgentType.TASK.value == "task"
        assert AgentType.ORCHESTRATOR.value == "orchestrator"

    def test_agent_type_from_string(self):
        """Test creating AgentType from string."""
        assert AgentType("foundational") == AgentType.FOUNDATIONAL
        assert AgentType("task") == AgentType.TASK
        assert AgentType("orchestrator") == AgentType.ORCHESTRATOR
