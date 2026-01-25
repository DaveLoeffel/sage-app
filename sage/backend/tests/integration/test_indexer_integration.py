"""
Integration tests for IndexerAgent with EmailProcessor and Chat API.

These tests verify end-to-end flows:
1. Email sync → IndexerAgent indexing → Search retrieval
2. Chat → Memory persistence → Memory retrieval
"""

import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

from sage.agents.foundational.indexer import IndexerAgent
from sage.agents.base import (
    DataLayerInterface,
    IndexedEntity,
    Relationship,
    SearchResult,
)


class MockDataLayerWithSearch(DataLayerInterface):
    """Mock DataLayerInterface with search capabilities for integration testing."""

    def __init__(self):
        self.stored_entities: dict[str, IndexedEntity] = {}
        self.relationships: list[dict] = []

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
        return True

    async def delete_entity(self, entity_id: str) -> bool:
        if entity_id in self.stored_entities:
            del self.stored_entities[entity_id]
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
    ) -> list[SearchResult]:
        """Simple keyword-based search for testing."""
        results = []
        query_lower = query.lower()

        for entity_id, entity in self.stored_entities.items():
            # Filter by type if specified
            if entity_types and entity.entity_type not in entity_types:
                continue

            # Simple text matching for testing
            searchable_text = ""
            if entity.structured:
                searchable_text = " ".join(str(v) for v in entity.structured.values() if v)

            if query_lower in searchable_text.lower():
                results.append(SearchResult(
                    entity=entity,
                    score=0.9,
                    match_type="semantic"
                ))

        return results[:limit]

    async def structured_query(
        self,
        filters: dict,
        entity_type: str,
        limit: int = 100,
    ) -> list[IndexedEntity]:
        results = []
        for entity in self.stored_entities.values():
            if entity.entity_type != entity_type:
                continue

            # Simple filter matching
            matches = True
            for key, value in filters.items():
                if entity.structured.get(key) != value:
                    matches = False
                    break

            if matches:
                results.append(entity)

        return results[:limit]

    async def get_relationships(
        self,
        entity_id: str,
        rel_types: list[str] | None = None,
    ) -> list[Relationship]:
        results = []
        for rel in self.relationships:
            if rel["from_id"] == entity_id or rel["to_id"] == entity_id:
                if rel_types is None or rel["rel_type"] in rel_types:
                    results.append(Relationship(
                        from_id=rel["from_id"],
                        to_id=rel["to_id"],
                        rel_type=rel["rel_type"],
                        metadata=rel["metadata"]
                    ))
        return results


@pytest.fixture
def mock_data_layer():
    """Create a mock data layer for integration testing."""
    return MockDataLayerWithSearch()


@pytest.fixture
def indexer_agent(mock_data_layer):
    """Create an IndexerAgent with mock data layer."""
    return IndexerAgent(data_layer=mock_data_layer)


# =============================================================================
# Email Flow Integration Tests
# =============================================================================

class TestEmailIndexingFlow:
    """Test email sync → index → search flow."""

    @pytest.mark.asyncio
    async def test_email_index_and_search(self, indexer_agent, mock_data_layer):
        """Test indexing an email and then searching for it."""
        # Step 1: Index an email
        index_result = await indexer_agent.execute(
            "index_email",
            {
                "gmail_id": "email_123",
                "thread_id": "thread_abc",
                "subject": "Meeting about Q1 Budget Review",
                "sender_email": "finance@company.com",
                "sender_name": "Finance Team",
                "to_emails": ["dave@company.com"],
                "body_text": "Please review the Q1 budget document attached. We need to discuss the marketing allocation.",
                "received_at": "2026-01-15T10:00:00",
                "labels": ["INBOX"],
            }
        )

        assert index_result.success is True
        entity_id = index_result.data["entity_id"]

        # Step 2: Search for the email by keyword
        results = await mock_data_layer.vector_search("budget", entity_types=["email"])

        assert len(results) == 1
        assert results[0].entity.id == entity_id
        assert "Budget Review" in results[0].entity.structured["subject"]

    @pytest.mark.asyncio
    async def test_email_creates_contact_relationship(self, indexer_agent, mock_data_layer):
        """Test that indexing email creates relationship to sender contact."""
        # Index an email
        await indexer_agent.execute(
            "index_email",
            {
                "gmail_id": "email_456",
                "sender_email": "john.smith@example.com",
                "sender_name": "John Smith",
                "subject": "Project Update",
            }
        )

        # Check that a relationship was created
        assert len(mock_data_layer.relationships) == 1
        rel = mock_data_layer.relationships[0]
        assert rel["rel_type"] == "received_from"
        assert "contact_john_smith_at_example_com" in rel["to_id"]

    @pytest.mark.asyncio
    async def test_multiple_emails_searchable(self, indexer_agent, mock_data_layer):
        """Test searching across multiple indexed emails."""
        # Index multiple emails
        emails = [
            {
                "gmail_id": "email_1",
                "subject": "Insurance renewal deadline",
                "sender_email": "insurance@broker.com",
                "body_text": "Your insurance policy expires on February 15.",
            },
            {
                "gmail_id": "email_2",
                "subject": "Team meeting notes",
                "sender_email": "team@company.com",
                "body_text": "Summary of today's standup meeting.",
            },
            {
                "gmail_id": "email_3",
                "subject": "Insurance claim update",
                "sender_email": "claims@broker.com",
                "body_text": "Your claim has been processed.",
            },
        ]

        for email in emails:
            await indexer_agent.execute("index_email", email)

        # Search for insurance-related emails
        results = await mock_data_layer.vector_search("insurance", entity_types=["email"])

        assert len(results) == 2
        subjects = [r.entity.structured["subject"] for r in results]
        assert "Insurance renewal deadline" in subjects
        assert "Insurance claim update" in subjects


# =============================================================================
# Memory Flow Integration Tests
# =============================================================================

class TestMemoryIndexingFlow:
    """Test chat → memory → retrieval flow."""

    @pytest.mark.asyncio
    async def test_memory_index_and_retrieve(self, indexer_agent, mock_data_layer):
        """Test indexing conversation memory and retrieving it."""
        # Mock fact extraction to avoid Claude API call
        with patch.object(indexer_agent, '_extract_facts', new_callable=AsyncMock) as mock_extract:
            mock_extract.return_value = MagicMock(
                success=True,
                data={
                    "facts": [
                        {
                            "type": "fact",
                            "content": "Insurance deadline is February 15",
                            "confidence": 0.95,
                            "entities_mentioned": ["insurance", "February 15"]
                        }
                    ]
                }
            )

            # Index a memory
            result = await indexer_agent.execute(
                "index_memory",
                {
                    "conversation_id": "conv_123",
                    "user_message": "The insurance renewal deadline is February 15, not January 31",
                    "sage_response": "Got it, I've updated the deadline to February 15th for the insurance renewal.",
                    "turn_number": 1,
                }
            )

        assert result.success is True
        assert result.data["facts_extracted"] == 1
        assert result.data["importance"] == "high"  # High confidence fact

        # Search for the memory
        results = await mock_data_layer.vector_search("insurance", entity_types=["memory"])

        assert len(results) == 1
        memory = results[0].entity
        assert memory.entity_type == "memory"
        assert "February 15" in memory.structured["user_message"]

    @pytest.mark.asyncio
    async def test_multiple_turns_in_conversation(self, indexer_agent, mock_data_layer):
        """Test indexing multiple turns in a conversation."""
        with patch.object(indexer_agent, '_extract_facts', new_callable=AsyncMock) as mock_extract:
            mock_extract.return_value = MagicMock(
                success=True,
                data={"facts": [], "skipped": True, "reason": "too_short"}
            )

            # Index multiple turns with unique timestamps to avoid ID collision
            base_time = "2026-01-20T10:00:0"
            for turn in range(1, 4):
                await indexer_agent.execute(
                    "index_memory",
                    {
                        "conversation_id": "conv_multi",
                        "user_message": f"Turn {turn} question",
                        "sage_response": f"Turn {turn} answer",
                        "turn_number": turn,
                        "timestamp": f"{base_time}{turn}",  # Unique timestamp per turn
                        "extract_facts": False,  # Skip extraction
                    }
                )

        # All turns should be stored
        memories = [e for e in mock_data_layer.stored_entities.values()
                   if e.entity_type == "memory"]
        assert len(memories) == 3

        # Verify turn numbers
        turn_numbers = [m.structured["turn_number"] for m in memories]
        assert sorted(turn_numbers) == [1, 2, 3]


# =============================================================================
# Contact Flow Integration Tests
# =============================================================================

class TestContactIndexingFlow:
    """Test contact creation and relationship flow."""

    @pytest.mark.asyncio
    async def test_contact_with_hierarchy(self, indexer_agent, mock_data_layer):
        """Test creating contacts with reports_to relationships."""
        # Create CEO
        await indexer_agent.execute(
            "index_contact",
            {
                "email": "ceo@company.com",
                "name": "Jane CEO",
                "role": "CEO",
                "category": "team",
            }
        )

        # Create VP reporting to CEO
        await indexer_agent.execute(
            "index_contact",
            {
                "email": "vp@company.com",
                "name": "Bob VP",
                "role": "VP Engineering",
                "category": "team",
                "reports_to": "ceo@company.com",
            }
        )

        # Check relationships
        assert len(mock_data_layer.relationships) == 1
        rel = mock_data_layer.relationships[0]
        assert rel["rel_type"] == "reports_to"

    @pytest.mark.asyncio
    async def test_contact_search(self, indexer_agent, mock_data_layer):
        """Test searching for contacts."""
        # Create contacts
        contacts = [
            {"email": "alice@acme.com", "name": "Alice Engineer", "company": "Acme"},
            {"email": "bob@widgets.com", "name": "Bob Sales", "company": "Widgets Inc"},
            {"email": "carol@acme.com", "name": "Carol Manager", "company": "Acme"},
        ]

        for contact in contacts:
            await indexer_agent.execute("index_contact", contact)

        # Search for Acme contacts
        results = await mock_data_layer.vector_search("Acme", entity_types=["contact"])

        assert len(results) == 2
        names = [r.entity.structured["name"] for r in results]
        assert "Alice Engineer" in names
        assert "Carol Manager" in names


# =============================================================================
# Fact Supersession Integration Tests
# =============================================================================

class TestFactSupersessionFlow:
    """Test fact correction and supersession flow."""

    @pytest.mark.asyncio
    async def test_fact_supersession_flow(self, indexer_agent, mock_data_layer):
        """Test the full fact supersession flow."""
        with patch.object(indexer_agent, '_extract_facts', new_callable=AsyncMock) as mock_extract:
            # First conversation: wrong deadline
            mock_extract.return_value = MagicMock(
                success=True,
                data={
                    "facts": [{
                        "type": "fact",
                        "content": "Deadline is January 31",
                        "confidence": 0.9,
                        "entities_mentioned": ["deadline", "January 31"]
                    }]
                }
            )

            result1 = await indexer_agent.execute(
                "index_memory",
                {
                    "conversation_id": "conv_1",
                    "user_message": "The deadline is January 31",
                    "sage_response": "Noted, deadline is January 31.",
                    "turn_number": 1,
                }
            )
            old_memory_id = result1.data["entity_id"]

            # Second conversation: corrected deadline
            mock_extract.return_value = MagicMock(
                success=True,
                data={
                    "facts": [{
                        "type": "fact_correction",
                        "content": "Deadline is February 15",
                        "confidence": 1.0,
                        "entities_mentioned": ["deadline", "February 15"]
                    }]
                }
            )

            result2 = await indexer_agent.execute(
                "index_memory",
                {
                    "conversation_id": "conv_2",
                    "user_message": "Actually the deadline is February 15",
                    "sage_response": "Updated to February 15.",
                    "turn_number": 1,
                }
            )
            new_memory_id = result2.data["entity_id"]

        # Supersede the old fact
        supersede_result = await indexer_agent.execute(
            "supersede_fact",
            {
                "old_fact_id": old_memory_id,
                "new_fact_id": new_memory_id,
                "reason": "User corrected the deadline"
            }
        )

        assert supersede_result.success is True

        # Verify old fact is marked as superseded
        old_memory = mock_data_layer.stored_entities[old_memory_id]
        assert old_memory.metadata.get("superseded_by") == new_memory_id
        assert old_memory.metadata.get("is_current") is False

        # Verify relationship was created
        rels = [r for r in mock_data_layer.relationships if r["rel_type"] == "supersedes"]
        assert len(rels) == 1
        assert rels[0]["from_id"] == new_memory_id
        assert rels[0]["to_id"] == old_memory_id


# =============================================================================
# Meeting and Event Integration Tests
# =============================================================================

class TestMeetingEventFlow:
    """Test meeting and event indexing with participants."""

    @pytest.mark.asyncio
    async def test_meeting_with_participants_links(self, indexer_agent, mock_data_layer):
        """Test that meeting indexing creates participant relationships."""
        # First create contacts
        participants = ["alice@company.com", "bob@company.com"]
        for email in participants:
            await indexer_agent.execute(
                "index_contact",
                {"email": email, "name": email.split("@")[0].title()}
            )

        # Index a meeting
        result = await indexer_agent.execute(
            "index_meeting",
            {
                "title": "Weekly Standup",
                "date": "2026-01-20T10:00:00",
                "participants": participants,
                "summary": "Discussed sprint progress",
                "source": "fireflies"
            }
        )

        assert result.success is True

        # Check participant relationships
        participant_rels = [r for r in mock_data_layer.relationships
                          if r["rel_type"] == "has_participant"]
        assert len(participant_rels) == 2

    @pytest.mark.asyncio
    async def test_event_search(self, indexer_agent, mock_data_layer):
        """Test searching for calendar events."""
        # Index events
        await indexer_agent.execute(
            "index_event",
            {
                "title": "Q1 Planning Session",
                "start_time": "2026-01-25T09:00:00",
                "end_time": "2026-01-25T17:00:00",
                "location": "Conference Room A",
                "attendees": ["team@company.com"]
            }
        )

        await indexer_agent.execute(
            "index_event",
            {
                "title": "Weekly Review",
                "start_time": "2026-01-20T14:00:00",
                "end_time": "2026-01-20T15:00:00",
            }
        )

        # Search for planning events
        results = await mock_data_layer.vector_search("Planning", entity_types=["event"])

        assert len(results) == 1
        assert results[0].entity.structured["title"] == "Q1 Planning Session"


# =============================================================================
# EmailProcessor Integration Tests
# =============================================================================

class TestEmailProcessorWithIndexer:
    """Test EmailProcessor with IndexerAgent integration."""

    @pytest.mark.asyncio
    async def test_email_processor_uses_indexer(self, indexer_agent, mock_data_layer):
        """Test that EmailProcessor uses IndexerAgent when provided."""
        from sage.models.email import EmailCache

        # Create a mock EmailCache object
        email = MagicMock(spec=EmailCache)
        email.gmail_id = "test_email_123"
        email.thread_id = "thread_xyz"
        email.subject = "Test Subject"
        email.sender_email = "test@example.com"
        email.sender_name = "Test Sender"
        email.to_emails = ["recipient@example.com"]
        email.cc_emails = []
        email.body_text = "Test email body content"
        email.snippet = "Test..."
        email.received_at = datetime(2026, 1, 20, 10, 0, 0)
        email.labels = ["INBOX"]
        email.has_attachments = False
        email.category = None
        email.priority = None
        email.summary = None
        email.requires_response = None
        email.qdrant_id = None

        # Create EmailProcessor with IndexerAgent
        from sage.core.email_processor import EmailProcessor

        # Mock db session
        mock_db = AsyncMock()
        mock_db.commit = AsyncMock()

        processor = EmailProcessor(db=mock_db, indexer_agent=indexer_agent)

        # Call _index_email
        await processor._index_email(email)

        # Verify email was indexed via IndexerAgent
        assert "email_test_email_123" in mock_data_layer.stored_entities
        indexed = mock_data_layer.stored_entities["email_test_email_123"]
        assert indexed.structured["subject"] == "Test Subject"
