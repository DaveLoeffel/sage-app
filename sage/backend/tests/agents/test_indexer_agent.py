"""
Unit tests for the IndexerAgent.

Tests all 11 capabilities of the Indexer Agent using mock DataLayerInterface.
"""

import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

from sage.agents.foundational.indexer import IndexerAgent
from sage.agents.base import (
    DataLayerInterface,
    IndexedEntity,
    AgentResult,
    Relationship,
)


class MockDataLayer(DataLayerInterface):
    """Mock DataLayerInterface for testing."""

    def __init__(self):
        self.stored_entities: dict[str, IndexedEntity] = {}
        self.relationships: list[dict] = []
        self.deleted_entities: list[str] = []

    async def store_entity(self, entity: IndexedEntity) -> str:
        self.stored_entities[entity.id] = entity
        return entity.id

    async def update_entity(self, entity_id: str, updates: dict) -> bool:
        if entity_id not in self.stored_entities:
            return False
        entity = self.stored_entities[entity_id]
        if "metadata" in updates:
            entity.metadata.update(updates["metadata"])
        if "analyzed" in updates:
            entity.analyzed.update(updates["analyzed"])
        if "structured" in updates:
            entity.structured.update(updates["structured"])
        return True

    async def delete_entity(self, entity_id: str) -> bool:
        if entity_id in self.stored_entities:
            del self.stored_entities[entity_id]
            self.deleted_entities.append(entity_id)
            return True
        return False

    async def get_entity(self, entity_id: str) -> IndexedEntity | None:
        return self.stored_entities.get(entity_id)

    async def create_relationship(
        self,
        from_id: str,
        to_id: str,
        rel_type: str,
        metadata: dict | None = None,
    ) -> bool:
        self.relationships.append({
            "from_id": from_id,
            "to_id": to_id,
            "rel_type": rel_type,
            "metadata": metadata or {}
        })
        return True

    async def vector_search(
        self,
        query: str,
        entity_types: list[str] | None = None,
        limit: int = 10,
    ) -> list:
        return []

    async def structured_query(
        self,
        filters: dict,
        entity_type: str,
        limit: int = 100,
    ) -> list[IndexedEntity]:
        return []

    async def get_relationships(
        self,
        entity_id: str,
        rel_types: list[str] | None = None,
    ) -> list[Relationship]:
        return []


@pytest.fixture
def mock_data_layer():
    """Create a mock data layer for testing."""
    return MockDataLayer()


@pytest.fixture
def indexer_agent(mock_data_layer):
    """Create an IndexerAgent with mock data layer."""
    return IndexerAgent(data_layer=mock_data_layer)


# =============================================================================
# Basic Agent Tests
# =============================================================================

class TestIndexerAgentBasics:
    """Test basic agent properties and setup."""

    def test_agent_name(self, indexer_agent):
        """Test agent has correct name."""
        assert indexer_agent.name == "indexer"

    def test_agent_capabilities(self, indexer_agent):
        """Test agent has all expected capabilities."""
        expected = [
            "index_email",
            "index_meeting",
            "index_contact",
            "index_document",
            "index_event",
            "index_memory",
            "extract_facts",
            "reindex_entity",
            "delete_entity",
            "link_entities",
            "supersede_fact",
        ]
        assert indexer_agent.capabilities == expected

    def test_supports_capability(self, indexer_agent):
        """Test capability support checking."""
        assert indexer_agent.supports_capability("index_email")
        assert indexer_agent.supports_capability("extract_facts")
        assert not indexer_agent.supports_capability("unknown_capability")


# =============================================================================
# Delete Entity Tests
# =============================================================================

class TestDeleteEntity:
    """Test delete_entity capability."""

    @pytest.mark.asyncio
    async def test_delete_existing_entity(self, indexer_agent, mock_data_layer):
        """Test deleting an existing entity."""
        # Pre-populate an entity
        entity = IndexedEntity(
            id="test_123",
            entity_type="test",
            source="test",
            structured={},
            analyzed={},
            relationships={},
            embeddings={},
            metadata={}
        )
        mock_data_layer.stored_entities["test_123"] = entity

        result = await indexer_agent.execute(
            "delete_entity",
            {"entity_id": "test_123"}
        )

        assert result.success is True
        assert result.data["deleted"] is True
        assert "test_123" in mock_data_layer.deleted_entities

    @pytest.mark.asyncio
    async def test_delete_nonexistent_entity(self, indexer_agent):
        """Test deleting a non-existent entity."""
        result = await indexer_agent.execute(
            "delete_entity",
            {"entity_id": "nonexistent_123"}
        )

        assert result.success is False
        assert "not found" in result.errors[0]

    @pytest.mark.asyncio
    async def test_delete_missing_entity_id(self, indexer_agent):
        """Test delete without entity_id."""
        result = await indexer_agent.execute("delete_entity", {})

        assert result.success is False
        assert "entity_id is required" in result.errors[0]


# =============================================================================
# Link Entities Tests
# =============================================================================

class TestLinkEntities:
    """Test link_entities capability."""

    @pytest.mark.asyncio
    async def test_link_entities_success(self, indexer_agent, mock_data_layer):
        """Test creating a relationship between entities."""
        result = await indexer_agent.execute(
            "link_entities",
            {
                "from_id": "email_123",
                "to_id": "contact_456",
                "rel_type": "sent_to",
                "metadata": {"cc": False}
            }
        )

        assert result.success is True
        assert len(mock_data_layer.relationships) == 1
        rel = mock_data_layer.relationships[0]
        assert rel["from_id"] == "email_123"
        assert rel["to_id"] == "contact_456"
        assert rel["rel_type"] == "sent_to"

    @pytest.mark.asyncio
    async def test_link_entities_missing_params(self, indexer_agent):
        """Test link_entities with missing required params."""
        result = await indexer_agent.execute(
            "link_entities",
            {"from_id": "email_123"}
        )

        assert result.success is False
        assert "required" in result.errors[0]


# =============================================================================
# Reindex Entity Tests
# =============================================================================

class TestReindexEntity:
    """Test reindex_entity capability."""

    @pytest.mark.asyncio
    async def test_reindex_existing_entity(self, indexer_agent, mock_data_layer):
        """Test reindexing an existing entity."""
        # Pre-populate an entity
        entity = IndexedEntity(
            id="email_123",
            entity_type="email",
            source="gmail",
            structured={"subject": "Test"},
            analyzed={},
            relationships={},
            embeddings={},
            metadata={"reindex_count": 0}
        )
        mock_data_layer.stored_entities["email_123"] = entity

        result = await indexer_agent.execute(
            "reindex_entity",
            {"entity_id": "email_123"}
        )

        assert result.success is True
        assert result.data["reindexed"] is True
        # Check metadata was updated
        reindexed = mock_data_layer.stored_entities["email_123"]
        assert "reindexed_at" in reindexed.metadata
        assert reindexed.metadata["reindex_count"] == 1

    @pytest.mark.asyncio
    async def test_reindex_nonexistent_entity(self, indexer_agent):
        """Test reindexing a non-existent entity."""
        result = await indexer_agent.execute(
            "reindex_entity",
            {"entity_id": "nonexistent_123"}
        )

        assert result.success is False
        assert "not found" in result.errors[0]


# =============================================================================
# Index Email Tests
# =============================================================================

class TestIndexEmail:
    """Test index_email capability."""

    @pytest.mark.asyncio
    async def test_index_email_with_parsed_params(self, indexer_agent, mock_data_layer):
        """Test indexing email with pre-parsed parameters."""
        result = await indexer_agent.execute(
            "index_email",
            {
                "gmail_id": "abc123",
                "thread_id": "thread_xyz",
                "subject": "Test Email Subject",
                "sender_email": "sender@example.com",
                "sender_name": "Test Sender",
                "to_emails": ["recipient@example.com"],
                "body_text": "This is the email body.",
                "received_at": "2026-01-20T10:00:00",
                "labels": ["INBOX"],
                "category": "action_required",
                "priority": "high"
            }
        )

        assert result.success is True
        assert result.data["indexed"] is True
        assert result.data["gmail_id"] == "abc123"

        # Check entity was stored
        entity_id = result.data["entity_id"]
        assert entity_id in mock_data_layer.stored_entities

        entity = mock_data_layer.stored_entities[entity_id]
        assert entity.entity_type == "email"
        assert entity.structured["subject"] == "Test Email Subject"
        assert entity.analyzed["category"] == "action_required"

    @pytest.mark.asyncio
    async def test_index_email_creates_sender_relationship(self, indexer_agent, mock_data_layer):
        """Test that indexing email creates relationship to sender."""
        await indexer_agent.execute(
            "index_email",
            {
                "gmail_id": "abc123",
                "sender_email": "sender@example.com",
                "subject": "Test"
            }
        )

        # Check relationship was created
        assert len(mock_data_layer.relationships) == 1
        rel = mock_data_layer.relationships[0]
        assert rel["rel_type"] == "received_from"
        assert "contact_" in rel["to_id"]

    @pytest.mark.asyncio
    async def test_index_email_missing_gmail_id(self, indexer_agent):
        """Test indexing email without gmail_id fails."""
        result = await indexer_agent.execute(
            "index_email",
            {"subject": "Test Email"}
        )

        assert result.success is False
        assert "gmail_id is required" in result.errors[0]

    @pytest.mark.asyncio
    async def test_index_email_with_raw_gmail_data(self, indexer_agent, mock_data_layer):
        """Test indexing email with raw Gmail API response."""
        gmail_response = {
            "id": "raw_email_123",
            "threadId": "thread_abc",
            "internalDate": "1705752000000",  # Unix timestamp in ms
            "labelIds": ["INBOX", "UNREAD"],
            "snippet": "This is a test...",
            "payload": {
                "mimeType": "text/plain",
                "headers": [
                    {"name": "From", "value": "Test User <test@example.com>"},
                    {"name": "To", "value": "recipient@example.com"},
                    {"name": "Subject", "value": "Raw Gmail Test"},
                ],
                "body": {
                    "data": "VGhpcyBpcyB0aGUgYm9keQ=="  # Base64: "This is the body"
                }
            }
        }

        result = await indexer_agent.execute(
            "index_email",
            {"email_data": gmail_response}
        )

        assert result.success is True
        assert result.data["gmail_id"] == "raw_email_123"


# =============================================================================
# Index Contact Tests
# =============================================================================

class TestIndexContact:
    """Test index_contact capability."""

    @pytest.mark.asyncio
    async def test_index_contact_basic(self, indexer_agent, mock_data_layer):
        """Test indexing a basic contact."""
        result = await indexer_agent.execute(
            "index_contact",
            {
                "email": "john@example.com",
                "name": "John Doe",
                "company": "Acme Inc",
                "role": "CEO"
            }
        )

        assert result.success is True
        assert result.data["indexed"] is True
        assert result.data["email"] == "john@example.com"

        # Check entity stored
        entity_id = result.data["entity_id"]
        entity = mock_data_layer.stored_entities[entity_id]
        assert entity.entity_type == "contact"
        assert entity.structured["name"] == "John Doe"

    @pytest.mark.asyncio
    async def test_index_contact_with_reports_to(self, indexer_agent, mock_data_layer):
        """Test indexing contact with supervisor relationship."""
        await indexer_agent.execute(
            "index_contact",
            {
                "email": "employee@example.com",
                "name": "Employee",
                "reports_to": "boss@example.com"
            }
        )

        # Check reports_to relationship created
        assert len(mock_data_layer.relationships) == 1
        rel = mock_data_layer.relationships[0]
        assert rel["rel_type"] == "reports_to"

    @pytest.mark.asyncio
    async def test_index_contact_missing_email(self, indexer_agent):
        """Test indexing contact without email fails."""
        result = await indexer_agent.execute(
            "index_contact",
            {"name": "John Doe"}
        )

        assert result.success is False
        assert "email is required" in result.errors[0]

    @pytest.mark.asyncio
    async def test_index_contact_generates_consistent_id(self, indexer_agent, mock_data_layer):
        """Test that same email generates same contact ID."""
        await indexer_agent.execute(
            "index_contact",
            {"email": "Test@Example.COM", "name": "Test 1"}
        )
        await indexer_agent.execute(
            "index_contact",
            {"email": "test@example.com", "name": "Test 2"}
        )

        # Same email (case-insensitive) should produce same ID
        # Second call overwrites first
        assert len(mock_data_layer.stored_entities) == 1


# =============================================================================
# Index Memory Tests
# =============================================================================

class TestIndexMemory:
    """Test index_memory capability."""

    @pytest.mark.asyncio
    async def test_index_memory_basic(self, indexer_agent, mock_data_layer):
        """Test indexing a conversation memory."""
        with patch.object(indexer_agent, '_extract_facts', new_callable=AsyncMock) as mock_extract:
            mock_extract.return_value = AgentResult(
                success=True,
                data={"facts": [], "count": 0}
            )

            result = await indexer_agent.execute(
                "index_memory",
                {
                    "conversation_id": "conv_123",
                    "user_message": "The deadline is February 15th",
                    "sage_response": "I've noted the deadline.",
                    "turn_number": 1,
                    "extract_facts": False  # Skip fact extraction for this test
                }
            )

        assert result.success is True
        assert result.data["indexed"] is True
        assert result.data["conversation_id"] == "conv_123"

        # Check entity stored
        entity_id = result.data["entity_id"]
        entity = mock_data_layer.stored_entities[entity_id]
        assert entity.entity_type == "memory"
        assert entity.structured["user_message"] == "The deadline is February 15th"

    @pytest.mark.asyncio
    async def test_index_memory_missing_params(self, indexer_agent):
        """Test indexing memory with missing params."""
        result = await indexer_agent.execute(
            "index_memory",
            {"conversation_id": "conv_123"}
        )

        assert result.success is False
        assert "required" in result.errors[0]


# =============================================================================
# Extract Facts Tests
# =============================================================================

class TestExtractFacts:
    """Test extract_facts capability."""

    @pytest.mark.asyncio
    async def test_extract_facts_too_short(self, indexer_agent):
        """Test that short exchanges are skipped."""
        result = await indexer_agent.execute(
            "extract_facts",
            {
                "user_message": "Hi",
                "sage_response": "Hello!"
            }
        )

        assert result.success is True
        assert result.data.get("skipped") is True
        assert result.data.get("reason") == "too_short"

    @pytest.mark.asyncio
    async def test_extract_facts_with_claude(self, indexer_agent):
        """Test fact extraction with mocked Claude response."""
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text='[{"type": "fact", "content": "Deadline is Feb 15", "confidence": 0.9, "entities_mentioned": ["Feb 15"]}]')]

        with patch.object(indexer_agent, '_get_claude', new_callable=AsyncMock) as mock_get_claude:
            mock_client = AsyncMock()
            mock_client.messages.create = AsyncMock(return_value=mock_response)
            mock_get_claude.return_value = mock_client

            result = await indexer_agent.execute(
                "extract_facts",
                {
                    "user_message": "The insurance renewal deadline is February 15, not January 31",
                    "sage_response": "Got it, I've updated the deadline to February 15th."
                }
            )

        assert result.success is True
        assert len(result.data["facts"]) == 1
        assert result.data["facts"][0]["content"] == "Deadline is Feb 15"


# =============================================================================
# Supersede Fact Tests
# =============================================================================

class TestSupersedeFact:
    """Test supersede_fact capability."""

    @pytest.mark.asyncio
    async def test_supersede_fact_success(self, indexer_agent, mock_data_layer):
        """Test marking a fact as superseded."""
        # Pre-populate old and new facts
        old_fact = IndexedEntity(
            id="memory_old",
            entity_type="memory",
            source="conversation",
            structured={},
            analyzed={},
            relationships={},
            embeddings={},
            metadata={}
        )
        new_fact = IndexedEntity(
            id="memory_new",
            entity_type="memory",
            source="conversation",
            structured={},
            analyzed={},
            relationships={},
            embeddings={},
            metadata={}
        )
        mock_data_layer.stored_entities["memory_old"] = old_fact
        mock_data_layer.stored_entities["memory_new"] = new_fact

        result = await indexer_agent.execute(
            "supersede_fact",
            {
                "old_fact_id": "memory_old",
                "new_fact_id": "memory_new",
                "reason": "Date was corrected"
            }
        )

        assert result.success is True
        assert result.data["superseded"] is True

        # Check old fact was updated
        old = mock_data_layer.stored_entities["memory_old"]
        assert old.metadata.get("superseded_by") == "memory_new"
        assert old.metadata.get("is_current") is False

        # Check relationship was created
        assert any(r["rel_type"] == "supersedes" for r in mock_data_layer.relationships)

    @pytest.mark.asyncio
    async def test_supersede_nonexistent_fact(self, indexer_agent):
        """Test superseding a non-existent fact."""
        result = await indexer_agent.execute(
            "supersede_fact",
            {
                "old_fact_id": "nonexistent",
                "new_fact_id": "new_fact"
            }
        )

        assert result.success is False
        assert "not found" in result.errors[0]


# =============================================================================
# Index Meeting Tests
# =============================================================================

class TestIndexMeeting:
    """Test index_meeting capability."""

    @pytest.mark.asyncio
    async def test_index_meeting_basic(self, indexer_agent, mock_data_layer):
        """Test indexing a meeting."""
        result = await indexer_agent.execute(
            "index_meeting",
            {
                "title": "Weekly Sync",
                "date": "2026-01-20T10:00:00",
                "participants": ["alice@example.com", "bob@example.com"],
                "summary": "Discussed Q1 priorities"
            }
        )

        assert result.success is True
        assert result.data["indexed"] is True
        assert result.data["title"] == "Weekly Sync"
        assert result.data["participants"] == 2

        # Check participant relationships created
        assert len(mock_data_layer.relationships) == 2
        assert all(r["rel_type"] == "has_participant" for r in mock_data_layer.relationships)

    @pytest.mark.asyncio
    async def test_index_meeting_missing_title(self, indexer_agent):
        """Test indexing meeting without title fails."""
        result = await indexer_agent.execute(
            "index_meeting",
            {"date": "2026-01-20"}
        )

        assert result.success is False
        assert "title is required" in result.errors[0]


# =============================================================================
# Index Event Tests
# =============================================================================

class TestIndexEvent:
    """Test index_event capability."""

    @pytest.mark.asyncio
    async def test_index_event_basic(self, indexer_agent, mock_data_layer):
        """Test indexing a calendar event."""
        result = await indexer_agent.execute(
            "index_event",
            {
                "title": "Team Meeting",
                "start_time": "2026-01-20T14:00:00",
                "end_time": "2026-01-20T15:00:00",
                "location": "Conference Room A",
                "attendees": ["alice@example.com"]
            }
        )

        assert result.success is True
        assert result.data["indexed"] is True
        assert result.data["title"] == "Team Meeting"

        # Check entity
        entity_id = result.data["entity_id"]
        entity = mock_data_layer.stored_entities[entity_id]
        assert entity.entity_type == "event"
        assert entity.structured["location"] == "Conference Room A"

    @pytest.mark.asyncio
    async def test_index_event_missing_required_fields(self, indexer_agent):
        """Test indexing event without required fields fails."""
        result = await indexer_agent.execute(
            "index_event",
            {"title": "Meeting"}  # Missing start_time
        )

        assert result.success is False
        assert "start_time" in result.errors[0]


# =============================================================================
# Index Document Tests
# =============================================================================

class TestIndexDocument:
    """Test index_document capability."""

    @pytest.mark.asyncio
    async def test_index_document_basic(self, indexer_agent, mock_data_layer):
        """Test indexing a document."""
        result = await indexer_agent.execute(
            "index_document",
            {
                "drive_file_id": "1abc123",
                "file_name": "Q4 Report.pdf",
                "mime_type": "application/pdf",
                "content": "This is the document content..."
            }
        )

        assert result.success is True
        assert result.data["indexed"] is True
        assert result.data["file_name"] == "Q4 Report.pdf"

    @pytest.mark.asyncio
    async def test_index_document_missing_fields(self, indexer_agent):
        """Test indexing document without required fields fails."""
        result = await indexer_agent.execute(
            "index_document",
            {"file_name": "test.pdf"}  # Missing drive_file_id
        )

        assert result.success is False
        assert "drive_file_id" in result.errors[0]


# =============================================================================
# High-Level index_entity Method Tests
# =============================================================================

class TestIndexEntityMethod:
    """Test the high-level index_entity method."""

    @pytest.mark.asyncio
    async def test_index_entity_routes_to_email(self, indexer_agent, mock_data_layer):
        """Test index_entity routes email type correctly."""
        entity_id = await indexer_agent.index_entity({
            "entity_type": "email",
            "gmail_id": "test_123",
            "subject": "Test"
        })

        assert entity_id.startswith("email_")
        assert "email_test_123" in mock_data_layer.stored_entities

    @pytest.mark.asyncio
    async def test_index_entity_routes_to_contact(self, indexer_agent, mock_data_layer):
        """Test index_entity routes contact type correctly."""
        entity_id = await indexer_agent.index_entity({
            "entity_type": "contact",
            "email": "test@example.com",
            "name": "Test User"
        })

        assert entity_id.startswith("contact_")

    @pytest.mark.asyncio
    async def test_index_entity_generic_fallback(self, indexer_agent, mock_data_layer):
        """Test index_entity handles unknown types with generic indexing."""
        entity_id = await indexer_agent.index_entity({
            "entity_type": "custom_type",
            "id": "custom_123",
            "source": "test",
            "structured": {"key": "value"}
        })

        assert entity_id == "custom_123"
        entity = mock_data_layer.stored_entities["custom_123"]
        assert entity.entity_type == "custom_type"


# =============================================================================
# Error Handling Tests
# =============================================================================

class TestErrorHandling:
    """Test error handling in IndexerAgent."""

    @pytest.mark.asyncio
    async def test_unknown_capability_returns_error(self, indexer_agent):
        """Test that unknown capability returns proper error."""
        with pytest.raises(ValueError, match="does not support capability"):
            await indexer_agent.execute("unknown_capability", {})

    @pytest.mark.asyncio
    async def test_data_layer_error_handled(self, indexer_agent, mock_data_layer):
        """Test that data layer errors are handled gracefully."""
        # Make store_entity raise an exception
        async def raise_error(*args, **kwargs):
            raise Exception("Database connection failed")

        mock_data_layer.store_entity = raise_error

        result = await indexer_agent.execute(
            "index_email",
            {"gmail_id": "test_123", "subject": "Test"}
        )

        assert result.success is False
        assert "Indexing error" in result.errors[0]
