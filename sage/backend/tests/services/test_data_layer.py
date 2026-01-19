"""
Unit tests for DataLayerService.

Tests the data layer service, adapters, and vector search integration.
"""

from datetime import datetime, timedelta
from unittest.mock import MagicMock, AsyncMock, patch
import pytest

from sage.agents.base import IndexedEntity, SearchResult, Relationship
from sage.services.data_layer.service import DataLayerService
from sage.services.data_layer.adapters.email import EmailAdapter
from sage.services.data_layer.adapters.contact import ContactAdapter
from sage.services.data_layer.adapters.followup import FollowupAdapter
from sage.services.data_layer.adapters.meeting import MeetingAdapter
from sage.services.data_layer.adapters.generic import GenericAdapter, MemoryAdapter
from sage.models.email import EmailCache, EmailCategory, EmailPriority
from sage.models.contact import Contact, ContactCategory
from sage.models.followup import Followup, FollowupStatus, FollowupPriority
from sage.models.meeting import MeetingNote


class TestEmailAdapter:
    """Test EmailAdapter conversion methods."""

    def setup_method(self):
        self.adapter = EmailAdapter()

    def test_to_indexed_entity(self):
        """Test converting EmailCache to IndexedEntity."""
        # Create a mock EmailCache model
        model = MagicMock(spec=EmailCache)
        model.id = 1
        model.gmail_id = "test_gmail_123"
        model.thread_id = "thread_456"
        model.subject = "Test Subject"
        model.sender_email = "sender@example.com"
        model.sender_name = "Test Sender"
        model.to_emails = ["recipient@example.com"]
        model.cc_emails = None
        model.body_text = "Test body content"
        model.snippet = "Test snippet..."
        model.labels = ["INBOX", "UNREAD"]
        model.is_unread = True
        model.has_attachments = False
        model.received_at = datetime(2026, 1, 15, 10, 30, 0)
        model.category = EmailCategory.ACTION_REQUIRED
        model.priority = EmailPriority.HIGH
        model.summary = "Test summary"
        model.action_items = "Do something"
        model.sentiment = "neutral"
        model.requires_response = True
        model.history_id = "history_789"
        model.qdrant_id = "qdrant_abc"
        model.synced_at = datetime(2026, 1, 15, 11, 0, 0)
        model.analyzed_at = datetime(2026, 1, 15, 11, 30, 0)

        entity = self.adapter.to_indexed_entity(model)

        assert entity.id == "email_test_gmail_123"
        assert entity.entity_type == "email"
        assert entity.source == "gmail"
        assert entity.structured["gmail_id"] == "test_gmail_123"
        assert entity.structured["subject"] == "Test Subject"
        assert entity.structured["sender_email"] == "sender@example.com"
        assert entity.analyzed["category"] == "action_required"
        assert entity.analyzed["priority"] == "high"
        assert entity.metadata["db_id"] == 1

    def test_from_indexed_entity(self):
        """Test converting IndexedEntity to dict for EmailCache."""
        entity = IndexedEntity(
            id="email_test_gmail_123",
            entity_type="email",
            source="gmail",
            structured={
                "gmail_id": "test_gmail_123",
                "thread_id": "thread_456",
                "subject": "Test Subject",
                "sender_email": "sender@example.com",
                "sender_name": "Test Sender",
                "is_unread": True,
                "has_attachments": False,
            },
            analyzed={
                "category": "urgent",
                "priority": "high",
                "summary": "Test summary",
            },
            metadata={
                "qdrant_id": "qdrant_abc",
            },
        )

        data = self.adapter.from_indexed_entity(entity)

        assert data["gmail_id"] == "test_gmail_123"
        assert data["subject"] == "Test Subject"
        assert data["is_unread"] is True
        assert data["category"] == "urgent"
        assert data["qdrant_id"] == "qdrant_abc"

    def test_get_embedding_text(self):
        """Test generating embedding text for email."""
        entity = IndexedEntity(
            id="email_test",
            entity_type="email",
            source="gmail",
            structured={
                "subject": "Project Update",
                "sender_name": "Alice",
                "sender_email": "alice@example.com",
                "body_text": "Here is the project status...",
            },
            analyzed={
                "summary": "Brief project status update",
            },
        )

        text = self.adapter.get_embedding_text(entity)

        assert "Subject: Project Update" in text
        assert "From: Alice <alice@example.com>" in text
        assert "Summary: Brief project status update" in text
        assert "Here is the project status..." in text

    def test_parse_entity_id(self):
        """Test parsing entity ID."""
        assert self.adapter.parse_entity_id("email_abc123") == "abc123"
        assert self.adapter.parse_entity_id("email_") == ""

    def test_make_entity_id(self):
        """Test creating entity ID."""
        assert self.adapter.make_entity_id("abc123") == "email_abc123"


class TestContactAdapter:
    """Test ContactAdapter conversion methods."""

    def setup_method(self):
        self.adapter = ContactAdapter()

    def test_to_indexed_entity(self):
        """Test converting Contact to IndexedEntity."""
        model = MagicMock(spec=Contact)
        model.id = 42
        model.email = "contact@example.com"
        model.name = "John Doe"
        model.company = "Acme Inc"
        model.role = "Engineer"
        model.phone = "555-1234"
        model.category = ContactCategory.CLIENT
        model.reports_to_id = None
        model.supervisor_email = None
        model.expected_response_days = 2
        model.notes = "Important client"
        model.ai_context = "Tech-savvy"
        model.last_email_at = datetime(2026, 1, 10, 9, 0, 0)
        model.last_meeting_at = None
        model.email_count = 15
        model.created_at = datetime(2026, 1, 1, 0, 0, 0)
        model.updated_at = datetime(2026, 1, 15, 12, 0, 0)

        entity = self.adapter.to_indexed_entity(model)

        assert entity.id == "contact_42"
        assert entity.entity_type == "contact"
        assert entity.structured["email"] == "contact@example.com"
        assert entity.structured["name"] == "John Doe"
        assert entity.structured["category"] == "client"
        assert entity.analyzed["notes"] == "Important client"
        assert entity.metadata["email_count"] == 15

    def test_get_embedding_text(self):
        """Test generating embedding text for contact."""
        entity = IndexedEntity(
            id="contact_42",
            entity_type="contact",
            source="database",
            structured={
                "name": "John Doe",
                "email": "john@example.com",
                "company": "Acme Inc",
                "role": "CTO",
                "category": "client",
            },
            analyzed={
                "notes": "Key decision maker",
                "ai_context": "Prefers email communication",
            },
        )

        text = self.adapter.get_embedding_text(entity)

        assert "Name: John Doe" in text
        assert "Company: Acme Inc" in text
        assert "Role: CTO" in text
        assert "Notes: Key decision maker" in text


class TestGenericAdapter:
    """Test GenericAdapter for memory, event, fact entities."""

    def test_memory_adapter(self):
        """Test MemoryAdapter."""
        adapter = MemoryAdapter()
        assert adapter.entity_type == "memory"

    def test_to_indexed_entity(self):
        """Test converting IndexedEntityModel to IndexedEntity."""
        adapter = GenericAdapter("memory")

        model = MagicMock()
        model.id = "memory_abc123"
        model.entity_type = "memory"
        model.source = "agent"
        model.structured = {"content": "Remember this fact"}
        model.analyzed = {"importance": "high"}
        model.metadata_ = {"context": "user preference"}
        model.qdrant_point_id = "qdrant_xyz"
        model.created_at = datetime(2026, 1, 15, 10, 0, 0)
        model.updated_at = datetime(2026, 1, 15, 11, 0, 0)

        entity = adapter.to_indexed_entity(model)

        assert entity.id == "memory_abc123"
        assert entity.entity_type == "memory"
        assert entity.source == "agent"
        assert entity.structured["content"] == "Remember this fact"
        assert entity.metadata["context"] == "user preference"
        assert entity.metadata["qdrant_point_id"] == "qdrant_xyz"

    def test_get_embedding_text(self):
        """Test generating embedding text for generic entity."""
        adapter = GenericAdapter("memory")

        entity = IndexedEntity(
            id="memory_abc",
            entity_type="memory",
            source="agent",
            structured={
                "title": "User Preference",
                "content": "Prefers morning briefings",
            },
            analyzed={
                "summary": "Scheduling preference",
            },
        )

        text = adapter.get_embedding_text(entity)

        assert "Type: memory" in text
        assert "Title: User Preference" in text
        assert "Content: Prefers morning briefings" in text
        assert "Summary: Scheduling preference" in text


class TestDataLayerService:
    """Test DataLayerService."""

    @pytest.fixture
    def mock_session(self):
        """Create a mock database session."""
        session = AsyncMock()
        session.execute = AsyncMock()
        session.add = MagicMock()
        session.delete = AsyncMock()
        session.flush = AsyncMock()
        return session

    @pytest.fixture
    def mock_vector_service(self):
        """Create a mock vector service."""
        service = MagicMock()
        service.index_entity = MagicMock(return_value="qdrant_point_123")
        service.search = MagicMock(return_value=[])
        service.delete_entity = MagicMock()
        service.get_collection_info = MagicMock(return_value={"points_count": 0})
        service.count_by_type = MagicMock(return_value={})
        return service

    @pytest.fixture
    def service(self, mock_session, mock_vector_service):
        """Create DataLayerService with mocks."""
        return DataLayerService(
            session=mock_session,
            vector_service=mock_vector_service,
        )

    def test_get_adapter(self, service):
        """Test getting adapters for different entity types."""
        assert isinstance(service._get_adapter("email"), EmailAdapter)
        assert isinstance(service._get_adapter("contact"), ContactAdapter)
        assert isinstance(service._get_adapter("followup"), FollowupAdapter)
        assert isinstance(service._get_adapter("meeting"), MeetingAdapter)
        assert isinstance(service._get_adapter("memory"), GenericAdapter)
        assert isinstance(service._get_adapter("unknown"), GenericAdapter)

    def test_parse_entity_type(self, service):
        """Test parsing entity type from ID."""
        assert service._parse_entity_type("email_abc123") == "email"
        assert service._parse_entity_type("contact_42") == "contact"
        assert service._parse_entity_type("memory_uuid-here") == "memory"

        with pytest.raises(ValueError):
            service._parse_entity_type("invalid")

    @pytest.mark.asyncio
    async def test_store_entity(self, service, mock_session, mock_vector_service):
        """Test storing an entity."""
        # Setup mock to simulate entity not existing
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        entity = IndexedEntity(
            id="memory_test123",
            entity_type="memory",
            source="test",
            structured={"content": "Test content"},
            analyzed={},
            metadata={},
        )

        result = await service.store_entity(entity)

        assert result == "memory_test123"
        mock_vector_service.index_entity.assert_called_once()
        call_args = mock_vector_service.index_entity.call_args
        assert call_args.kwargs["entity_id"] == "memory_test123"
        assert call_args.kwargs["entity_type"] == "memory"

    @pytest.mark.asyncio
    async def test_delete_entity(self, service, mock_session, mock_vector_service):
        """Test deleting an entity."""
        # Setup mock to simulate entity exists
        mock_model = MagicMock()
        mock_model.soft_delete = MagicMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_model
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute.return_value = mock_result

        result = await service.delete_entity("memory_test123")

        assert result is True
        mock_vector_service.delete_entity.assert_called_once_with("memory_test123")

    @pytest.mark.asyncio
    async def test_create_relationship(self, service, mock_session):
        """Test creating a relationship."""
        # Setup mock to simulate relationship doesn't exist
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        result = await service.create_relationship(
            from_id="email_abc",
            to_id="contact_123",
            rel_type="sent_to",
            metadata={"importance": "high"},
        )

        assert result is True
        mock_session.add.assert_called_once()

    @pytest.mark.asyncio
    async def test_vector_search(self, service, mock_session, mock_vector_service):
        """Test vector search."""
        # Setup vector search results
        mock_vector_service.search.return_value = [
            {
                "entity_id": "email_abc123",
                "entity_type": "email",
                "score": 0.85,
                "text_preview": "Test email...",
            }
        ]

        # Setup entity retrieval mock
        mock_model = MagicMock(spec=EmailCache)
        mock_model.id = 1
        mock_model.gmail_id = "abc123"
        mock_model.thread_id = "thread_1"
        mock_model.subject = "Test"
        mock_model.sender_email = "test@example.com"
        mock_model.sender_name = None
        mock_model.to_emails = None
        mock_model.cc_emails = None
        mock_model.body_text = "Test body"
        mock_model.snippet = None
        mock_model.labels = ["INBOX"]
        mock_model.is_unread = True
        mock_model.has_attachments = False
        mock_model.received_at = datetime.now()
        mock_model.category = None
        mock_model.priority = None
        mock_model.summary = None
        mock_model.action_items = None
        mock_model.sentiment = None
        mock_model.requires_response = None
        mock_model.history_id = None
        mock_model.qdrant_id = None
        mock_model.synced_at = datetime.now()
        mock_model.analyzed_at = None

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_model
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute.return_value = mock_result

        results = await service.vector_search(
            query="test query",
            entity_types=["email"],
            limit=10,
        )

        mock_vector_service.search.assert_called_once_with(
            query="test query",
            entity_types=["email"],
            limit=10,
        )
        assert len(results) == 1
        assert results[0].score == 0.85
        assert results[0].match_type == "semantic"

    @pytest.mark.asyncio
    async def test_get_relationships(self, service, mock_session):
        """Test getting relationships."""
        # Setup mock relationships
        mock_rel = MagicMock()
        mock_rel.from_entity_id = "email_abc"
        mock_rel.to_entity_id = "contact_123"
        mock_rel.relationship_type = "sent_to"
        mock_rel.metadata_ = {}

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_rel]
        mock_session.execute.return_value = mock_result

        relationships = await service.get_relationships("email_abc")

        assert len(relationships) == 1
        assert relationships[0].from_id == "email_abc"
        assert relationships[0].to_id == "contact_123"
        assert relationships[0].rel_type == "sent_to"

    def test_get_collection_stats(self, service, mock_vector_service):
        """Test getting collection stats."""
        mock_vector_service.get_collection_info.return_value = {
            "name": "sage_entities",
            "points_count": 100,
            "status": "green",
        }
        mock_vector_service.count_by_type.return_value = {
            "email": 50,
            "contact": 30,
            "memory": 20,
        }

        stats = service.get_collection_stats()

        assert stats["name"] == "sage_entities"
        assert stats["points_count"] == 100
        assert stats["counts_by_type"]["email"] == 50


class TestFollowupAdapter:
    """Test FollowupAdapter conversion methods."""

    def setup_method(self):
        self.adapter = FollowupAdapter()

    def test_to_indexed_entity(self):
        """Test converting Followup to IndexedEntity."""
        model = MagicMock(spec=Followup)
        model.id = 127
        model.user_id = 1
        model.email_id = 42
        model.gmail_id = "gmail_abc"
        model.thread_id = "thread_xyz"
        model.subject = "Follow up on proposal"
        model.contact_email = "client@example.com"
        model.contact_name = "Client Name"
        model.status = FollowupStatus.PENDING
        model.priority = FollowupPriority.HIGH
        model.due_date = datetime(2026, 1, 20)
        model.escalation_email = "manager@example.com"
        model.escalation_days = 7
        model.notes = "Important client"
        model.ai_summary = "Proposal follow-up"
        model.reminder_sent_at = None
        model.escalated_at = None
        model.completed_at = None
        model.completed_reason = None
        model.created_at = datetime(2026, 1, 15)
        model.updated_at = datetime(2026, 1, 15)

        entity = self.adapter.to_indexed_entity(model)

        assert entity.id == "followup_127"
        assert entity.entity_type == "followup"
        assert entity.structured["subject"] == "Follow up on proposal"
        assert entity.structured["status"] == "pending"
        assert entity.structured["priority"] == "high"


class TestMeetingAdapter:
    """Test MeetingAdapter conversion methods."""

    def setup_method(self):
        self.adapter = MeetingAdapter()

    def test_to_indexed_entity(self):
        """Test converting MeetingNote to IndexedEntity."""
        model = MagicMock(spec=MeetingNote)
        model.id = 5
        model.user_id = 1
        model.fireflies_id = "ff_meeting_123"
        model.title = "Weekly Standup"
        model.meeting_date = datetime(2026, 1, 14, 9, 0)
        model.duration_minutes = 30
        model.participants = ["alice@example.com", "bob@example.com"]
        model.summary = "Discussed project status"
        model.key_points = ["Point 1", "Point 2"]
        model.action_items = ["Review PR", "Update docs"]
        model.keywords = ["project", "status"]
        model.transcript = {"text": "Meeting transcript..."}
        model.last_synced_at = datetime(2026, 1, 14, 10, 0)
        model.created_at = datetime(2026, 1, 14, 10, 0)
        model.updated_at = datetime(2026, 1, 14, 10, 0)

        entity = self.adapter.to_indexed_entity(model)

        assert entity.id == "meeting_ff_meeting_123"
        assert entity.entity_type == "meeting"
        assert entity.source == "fireflies"
        assert entity.structured["title"] == "Weekly Standup"
        assert entity.structured["participants"] == ["alice@example.com", "bob@example.com"]
        assert entity.analyzed["summary"] == "Discussed project status"
        assert entity.analyzed["action_items"] == ["Review PR", "Update docs"]

    def test_get_embedding_text(self):
        """Test generating embedding text for meeting."""
        entity = IndexedEntity(
            id="meeting_ff_123",
            entity_type="meeting",
            source="fireflies",
            structured={
                "title": "Product Review",
                "meeting_date": "2026-01-14T10:00:00",
                "participants": ["alice@example.com", "bob@example.com"],
            },
            analyzed={
                "summary": "Reviewed Q1 product roadmap",
                "key_points": ["Feature A", "Feature B"],
                "action_items": ["Schedule follow-up", "Share docs"],
                "keywords": ["roadmap", "features"],
            },
        )

        text = self.adapter.get_embedding_text(entity)

        assert "Meeting: Product Review" in text
        assert "Participants: alice@example.com, bob@example.com" in text
        assert "Summary: Reviewed Q1 product roadmap" in text
        assert "Key Points:" in text
        assert "Action Items:" in text
