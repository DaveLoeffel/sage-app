# Indexer Agent Implementation Plan

**Created:** January 20, 2026
**Status:** Ready for Review
**Estimated Sessions:** 3-4 (6-8 hours total)

---

## Executive Summary

The Indexer Agent is the foundational component responsible for ingesting all data into Sage's Data Layer. It transforms raw data from external sources (Gmail, Calendar, Fireflies, conversations) into search-optimized formats stored in PostgreSQL and Qdrant.

**Current State:** Stub with 11 capabilities defined, all raise `NotImplementedError`
**Goal:** Fully functional Indexer Agent that handles all data ingestion for the system

---

## Architecture Context

```
┌─────────────────────────────────────────────────────────────────────┐
│                      LAYER 1: DATA LAYER                             │
│                                                                      │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                     INDEXER AGENT                            │   │
│  │        (ingests, transforms, optimizes for search)           │   │
│  │                                                               │   │
│  │  Capabilities:                                                │   │
│  │  - index_email         - index_memory      - delete_entity   │   │
│  │  - index_meeting       - extract_facts     - link_entities   │   │
│  │  - index_contact       - reindex_entity    - supersede_fact  │   │
│  │  - index_document                                             │   │
│  │  - index_event                                                │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                              │                                       │
│  ┌───────────────┐  ┌───────▼───────┐  ┌───────────────┐          │
│  │  PostgreSQL   │  │ DataLayer     │  │    Qdrant     │          │
│  │  (structured) │◄─│ Service       │─►│  (vectors)    │          │
│  └───────────────┘  └───────────────┘  └───────────────┘          │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Existing Infrastructure to Leverage

### Already Complete (Can Reuse)

| Component | Location | Purpose |
|-----------|----------|---------|
| **DataLayerService** | `services/data_layer/service.py` | Unified storage interface |
| **Entity Adapters** | `services/data_layer/adapters/` | Email, Contact, Followup, Meeting, Generic |
| **MultiEntityVectorService** | `services/data_layer/vector.py` | Qdrant indexing |
| **IndexedEntityModel** | `services/data_layer/models/` | DB model for memory/fact/event |
| **Email Processing** | `core/email_processor.py` | Gmail sync logic to refactor |
| **Claude Agent** | `core/claude_agent.py` | AI analysis for fact extraction |
| **VectorSearchService** | `services/vector_search.py` | Legacy email vector indexing |

### Needs Extraction/Refactoring

| Source | Extract To | Notes |
|--------|------------|-------|
| `EmailProcessor._process_email()` | `IndexerAgent._index_email()` | Core email indexing |
| `EmailProcessor._analyze_email()` | Reuse via composition | AI analysis |
| `EmailProcessor._index_email()` | `IndexerAgent._index_email()` | Vector indexing |
| `BulkEmailImporter` logic | Keep separate, call Indexer | Bulk operations |

---

## Implementation Plan

### Phase 1: Core Infrastructure (Session 1, ~2 hours)

#### 1.1 Refactor IndexerAgent Foundation

**File:** `sage/backend/sage/agents/foundational/indexer.py`

- [ ] Add imports for DataLayerService, Claude agent, models
- [ ] Add Claude client initialization for fact extraction
- [ ] Add helper methods for embedding generation
- [ ] Add entity ID generation utilities

```python
# Key additions
from sage.services.data_layer.service import DataLayerService
from sage.core.claude_agent import get_claude_agent, ClaudeAgent
from sage.services.data_layer.vector import get_multi_vector_service

class IndexerAgent(BaseAgent):
    def __init__(self, data_layer: DataLayerInterface):
        super().__init__(search_agent=None, indexer_agent=None)
        self.data_layer = data_layer
        self._claude_agent: ClaudeAgent | None = None

    async def _get_claude(self) -> ClaudeAgent:
        if not self._claude_agent:
            self._claude_agent = await get_claude_agent()
        return self._claude_agent
```

#### 1.2 Implement Simple Capabilities First

These use DataLayerService directly:

- [ ] **delete_entity** - Call `data_layer.delete_entity()`
- [ ] **link_entities** - Call `data_layer.create_relationship()`
- [ ] **reindex_entity** - Delete + re-index

```python
async def _delete_entity(self, params: dict) -> AgentResult:
    entity_id = params.get("entity_id")
    success = await self.data_layer.delete_entity(entity_id)
    return AgentResult(
        success=success,
        data={"entity_id": entity_id, "deleted": success}
    )

async def _link_entities(self, params: dict) -> AgentResult:
    rel = Relationship(
        from_id=params["from_id"],
        to_id=params["to_id"],
        rel_type=params["rel_type"],
        metadata=params.get("metadata", {})
    )
    await self.data_layer.create_relationship(rel)
    return AgentResult(success=True, data={"relationship": rel.__dict__})
```

---

### Phase 2: Email & Contact Indexing (Session 2, ~2 hours)

#### 2.1 Implement index_email

Refactor from `EmailProcessor._process_email()`:

- [ ] Accept raw Gmail API response or EmailCache model
- [ ] Parse headers, body, metadata
- [ ] Create `IndexedEntity` with proper schema
- [ ] Store via DataLayerService (auto-vectors)
- [ ] Optional: Trigger AI analysis

**Expected params:**
```python
{
    "email_data": {...},  # Gmail API response OR
    "email_cache": EmailCache,  # Existing model
    "analyze": True,  # Whether to run AI analysis
    "force_reindex": False
}
```

**Implementation approach:**
```python
async def _index_email(self, params: dict) -> AgentResult:
    email_data = params.get("email_data")
    email_cache = params.get("email_cache")
    analyze = params.get("analyze", True)

    # Parse if raw Gmail data
    if email_data:
        structured = self._parse_gmail_response(email_data)
    else:
        structured = self._email_cache_to_structured(email_cache)

    # Create IndexedEntity
    entity = IndexedEntity(
        id=f"email_{structured['gmail_id']}",
        entity_type="email",
        source="gmail",
        structured=structured,
        analyzed={},
        relationships={},
        embeddings={},
        metadata={"indexed_at": datetime.utcnow().isoformat()}
    )

    # Store (auto-creates embedding)
    entity_id = await self.data_layer.store_entity(entity)

    # Optional AI analysis
    if analyze:
        claude = await self._get_claude()
        analysis = await claude.analyze_email_from_data(structured)
        await self.data_layer.update_entity(entity_id, {"analyzed": analysis})

    return AgentResult(
        success=True,
        data={"entity_id": entity_id, "analyzed": analyze}
    )
```

#### 2.2 Implement index_contact

- [ ] Accept contact data dict or Contact model
- [ ] Create/update via DataLayerService
- [ ] Auto-link to related emails if available

**Expected params:**
```python
{
    "email": "user@example.com",
    "name": "John Doe",
    "company": "Acme Inc",
    "role": "CEO",
    "phone": "555-1234",
    "category": "external",  # team, external, vendor, family
    "reports_to": "contact_boss_id"  # Optional
}
```

---

### Phase 3: Meeting & Event Indexing (Session 2 continued)

#### 3.1 Implement index_meeting

Integrate with existing Fireflies MCP and meeting data:

- [ ] Accept Fireflies transcript ID or raw transcript data
- [ ] Parse participants, action items, summary
- [ ] Create IndexedEntity with meeting schema
- [ ] Link to contacts (participants)

**Expected params:**
```python
{
    "fireflies_id": "abc123",  # OR
    "transcript_data": {...},  # Raw transcript
    "title": "Weekly Sync",
    "participants": ["email1@...", "email2@..."],
    "date": "2026-01-20T10:00:00Z"
}
```

#### 3.2 Implement index_event

Calendar event indexing:

- [ ] Accept Google Calendar event data
- [ ] Parse attendees, time, location, description
- [ ] Create IndexedEntity
- [ ] Link to contacts (attendees)

**Expected params:**
```python
{
    "calendar_event": {...},  # Google Calendar API response
    "calendar_id": "primary"
}
```

---

### Phase 4: Conversation Memory (Session 3, ~2 hours)

This is the most important new capability - persistent conversation memory.

#### 4.1 Implement index_memory

Store each conversation exchange for future recall:

- [ ] Create memory entity with user message + sage response
- [ ] Extract facts, decisions, preferences
- [ ] Generate embeddings for semantic search
- [ ] Link to mentioned contacts, projects

**Expected params:**
```python
{
    "conversation_id": "conv_abc123",
    "user_message": "The deadline is actually Feb 15",
    "sage_response": "I've updated the deadline...",
    "timestamp": "2026-01-20T10:30:00Z"
}
```

**Memory schema:**
```json
{
    "id": "memory_conv_20260120_103000",
    "entity_type": "memory",
    "source": "conversation",
    "structured": {
        "conversation_id": "conv_abc123",
        "timestamp": "2026-01-20T10:30:00Z",
        "turn_number": 5,
        "user_message": "...",
        "sage_response": "..."
    },
    "analyzed": {
        "memory_type": "fact_correction",
        "importance": "high",
        "facts_extracted": [...],
        "entities_mentioned": [...]
    }
}
```

#### 4.2 Implement extract_facts

Use Claude to analyze text and extract structured facts:

- [ ] Send text to Claude with fact extraction prompt
- [ ] Parse response into fact objects
- [ ] Check for contradictions with existing facts
- [ ] Return structured facts list

**Fact extraction prompt:**
```
Analyze this text and extract:
1. Facts (new information stated)
2. Decisions (choices made)
3. Preferences (user preferences expressed)
4. Tasks (action items mentioned)

For each, provide:
- fact: The extracted information
- type: fact | decision | preference | task
- confidence: 0.0-1.0
- entities_mentioned: list of people, projects, dates
```

---

### Phase 5: Fact Supersession (Session 3 continued)

#### 5.1 Implement supersede_fact

When new information contradicts old:

- [ ] Retrieve old fact from data layer
- [ ] Mark old fact's metadata with `superseded_by`
- [ ] Update new fact's metadata with `supersedes`
- [ ] Both facts retained for audit trail

**Expected params:**
```python
{
    "old_fact_id": "memory_conv_20260115_091200",
    "new_fact_id": "memory_conv_20260120_103000",
    "reason": "User corrected deadline from Jan 31 to Feb 15"
}
```

**Implementation:**
```python
async def _supersede_fact(self, params: dict) -> AgentResult:
    old_id = params["old_fact_id"]
    new_id = params["new_fact_id"]
    reason = params.get("reason", "")

    # Update old fact
    await self.data_layer.update_entity(old_id, {
        "metadata": {
            "superseded_by": new_id,
            "superseded_at": datetime.utcnow().isoformat(),
            "supersession_reason": reason
        }
    })

    # Update new fact
    await self.data_layer.update_entity(new_id, {
        "metadata": {
            "supersedes": old_id
        }
    })

    return AgentResult(
        success=True,
        data={"old_fact_id": old_id, "new_fact_id": new_id}
    )
```

---

### Phase 6: Document Indexing (Session 4, ~1 hour)

#### 6.1 Implement index_document

Google Drive document indexing:

- [ ] Integrate with Google Drive API
- [ ] Extract text from supported formats (Docs, Sheets, PDF)
- [ ] Create IndexedEntity with document schema
- [ ] Generate embeddings for content search

**Expected params:**
```python
{
    "drive_file_id": "1abc...",
    "file_name": "Q4 Report.pdf",
    "mime_type": "application/pdf"
}
```

**Note:** This is lower priority - can be stubbed initially.

---

### Phase 7: Integration & Testing (Session 4, ~1 hour)

#### 7.1 Update Email Processing

Modify `EmailProcessor` to use `IndexerAgent`:

```python
class EmailProcessor:
    def __init__(self, db: AsyncSession, indexer: IndexerAgent):
        self.db = db
        self.indexer = indexer

    async def _process_email(self, email_data: dict) -> bool:
        result = await self.indexer.execute(
            "index_email",
            {"email_data": email_data, "analyze": True}
        )
        return result.success
```

#### 7.2 Create Unit Tests

- [ ] Test each capability with mock data
- [ ] Test email indexing with sample Gmail response
- [ ] Test memory indexing and fact extraction
- [ ] Test supersession logic
- [ ] Test error handling

**Test file:** `sage/backend/tests/agents/test_indexer_agent.py`

#### 7.3 Integration Tests

- [ ] End-to-end email sync → index → search
- [ ] Conversation → memory → fact extraction → search
- [ ] Meeting → index → action items → followups

---

## Database Migrations Required

None - existing tables support all needed functionality:

| Entity Type | Storage |
|-------------|---------|
| email | `email_cache` table (existing) |
| contact | `contacts` table (existing) |
| followup | `followups` table (existing) |
| meeting | `meeting_notes` table (existing) |
| memory | `indexed_entities` table (existing, via GenericAdapter) |
| fact | `indexed_entities` table (existing, via GenericAdapter) |
| event | `indexed_entities` table (existing, via GenericAdapter) |

---

## Success Criteria

1. **All 11 capabilities implemented** (no `NotImplementedError`)
2. **Email indexing** works end-to-end via `IndexerAgent`
3. **Conversation memory** stores and retrieves correctly
4. **Fact extraction** identifies facts, decisions, preferences
5. **Supersession** correctly marks old facts and links to new
6. **Unit tests** pass (target: 30+ tests)
7. **Documentation** updated in architecture doc

---

## Risk Assessment

| Risk | Mitigation |
|------|------------|
| Claude API costs for fact extraction | Use tiered approach - only extract from important exchanges |
| Memory volume over time | Implement memory summarization/pruning later |
| Breaking existing email sync | Refactor incrementally, keep both paths working |
| Google Drive API complexity | Stub initially, implement in later phase |

---

## Appendix: File Changes Summary

### Files to Modify

| File | Changes |
|------|---------|
| `agents/foundational/indexer.py` | Full implementation (~500 lines) |
| `core/email_processor.py` | Use IndexerAgent for indexing |
| `api/chat.py` | Call index_memory after each exchange |

### Files to Create

| File | Purpose |
|------|---------|
| `tests/agents/test_indexer_agent.py` | Unit tests (~400 lines) |

### Files to Update (docs)

| File | Changes |
|------|---------|
| `sage-implementation-roadmap.md` | Mark Indexer Agent complete |
| `sage-agent-architecture.md` | Add implementation notes |

---

## Quick Start Commands

```bash
# Run tests for indexer agent
docker compose exec backend pytest tests/agents/test_indexer_agent.py -v

# Test email indexing
docker compose exec backend python -c "
from sage.agents.foundational.indexer import IndexerAgent
# ... test code
"
```

---

*This plan prioritizes the most impactful capabilities (email, memory, facts) while stubbing lower-priority ones (documents) for later implementation.*
