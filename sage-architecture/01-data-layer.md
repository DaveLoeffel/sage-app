# Sage Agent Architecture: Data Layer

**Part of:** [Sage Architecture Documentation](00-overview.md)

---

## Layer 1: Data Layer

The Data Layer is the foundation—a unified, search-optimized repository of all information Sage knows.

### Storage Components

| Component | Purpose | Data Types |
|-----------|---------|------------|
| **PostgreSQL** | Structured data, relationships, transactions | Users, contacts, follow-ups, emails (metadata), meetings, properties |
| **Qdrant** | Vector embeddings for semantic search | Email content, meeting transcripts, documents, notes |
| **Redis** | Caching, session state, rate limiting | Recent queries, agent results, user sessions |
| **External APIs** | Live data sources | Gmail, Google Calendar, Fireflies, Entrata |

---

## The Indexer Agent

The Indexer Agent is responsible for ingesting data from all sources and preparing it for optimal retrieval.

### Purpose
Transform raw data into search-optimized formats across all storage systems.

### Responsibilities

1. **Ingest** — Pull data from external APIs (Gmail, Calendar, Fireflies)
2. **Transform** — Normalize, clean, and enrich data
3. **Embed** — Generate vector embeddings for semantic search
4. **Index** — Store in appropriate systems with proper metadata
5. **Link** — Create relationships between entities (email ↔ contact ↔ follow-up)
6. **Maintain** — Update stale data, remove duplicates, handle deletions

### Indexer Agent Specification

```yaml
agent:
  name: indexer
  type: foundational
  layer: data

capabilities:
  - index_email          # Process and store email with embeddings
  - index_meeting        # Process meeting transcript
  - index_contact        # Create/update contact profile
  - index_document       # Process document from Drive
  - index_event          # Process calendar event
  - index_memory         # Capture and index conversation exchanges
  - extract_facts        # Pull facts, decisions, preferences from conversation
  - reindex_entity       # Re-process existing entity
  - delete_entity        # Remove from all indices
  - link_entities        # Create relationship between entities
  - supersede_fact       # Mark old fact as superseded by new one

inputs:
  - raw_data: dict       # The data to index
  - source: str          # Where data came from (gmail, calendar, fireflies, etc.)
  - entity_type: str     # Type of entity (email, contact, meeting, etc.)
  - force_reindex: bool  # Whether to reprocess existing data

outputs:
  - entity_id: str       # ID of indexed entity
  - embeddings_created: int
  - relationships_created: list[tuple]
  - indexing_metadata: dict
```

---

## Index Schema Design

### Email Index Entry

```json
{
  "id": "email_abc123",
  "entity_type": "email",
  "source": "gmail",

  "structured": {
    "gmail_id": "abc123",
    "thread_id": "thread_xyz",
    "subject": "Q4 Investor Update Draft",
    "from_email": "lhodgson@highlandsresidential.com",
    "from_name": "Laura Hodgson",
    "to_emails": ["dloeffel@highlandsresidential.com"],
    "received_at": "2026-01-15T10:30:00Z",
    "labels": ["INBOX", "IMPORTANT"],
    "has_attachments": true
  },

  "analyzed": {
    "category": "action_required",
    "priority": "high",
    "sentiment": "neutral",
    "summary": "Laura sharing Q4 investor update draft for review before Jan 22 send date",
    "action_items": ["Review attached draft", "Provide feedback by Jan 20"],
    "key_entities": ["Q4 investor update", "Jan 22 deadline"],
    "requires_response": true,
    "response_deadline": "2026-01-20"
  },

  "relationships": {
    "contact_id": "contact_laura_hodgson",
    "thread_emails": ["email_abc122", "email_abc121"],
    "related_followups": ["followup_789"],
    "related_projects": ["project_q4_update"]
  },

  "embeddings": {
    "qdrant_id": "vec_email_abc123",
    "embedded_text": "Q4 Investor Update Draft - Laura sharing draft for review...",
    "embedding_model": "all-MiniLM-L6-v2",
    "embedded_at": "2026-01-15T10:31:00Z"
  },

  "metadata": {
    "indexed_at": "2026-01-15T10:31:00Z",
    "last_updated": "2026-01-15T10:31:00Z",
    "index_version": 2
  }
}
```

### Contact Index Entry

```json
{
  "id": "contact_laura_hodgson",
  "entity_type": "contact",
  "source": "manual",

  "structured": {
    "email": "lhodgson@highlandsresidential.com",
    "name": "Laura Hodgson",
    "company": "Highlands Residential",
    "role": "Business Financials & Investor Relations",
    "phone": null,
    "reports_to": "Dave Loeffel",
    "category": "team"
  },

  "analyzed": {
    "communication_style": "professional, thorough, reliable",
    "typical_response_time": "within 1 business day",
    "relationship_summary": "Key team member handling financials and investor communications",
    "interaction_frequency": "daily",
    "last_interaction_summary": "Sent Q4 investor update draft for review"
  },

  "statistics": {
    "total_emails": 847,
    "emails_last_30_days": 45,
    "avg_response_time_hours": 4.2,
    "open_followups": 2,
    "meetings_last_90_days": 12
  },

  "relationships": {
    "organization_id": "org_highlands",
    "supervised_by": null,
    "supervises": [],
    "frequent_cc": ["contact_welton_mccrary"],
    "shared_projects": ["project_q4_update", "project_chateau_expenses"]
  },

  "embeddings": {
    "qdrant_id": "vec_contact_laura_hodgson",
    "embedded_text": "Laura Hodgson - Business Financials & Investor Relations at Highlands Residential...",
    "embedding_model": "all-MiniLM-L6-v2"
  }
}
```

---

## Conversation Memory

The Indexer Agent automatically captures and indexes conversations with Sage. This ensures nothing discussed is ever forgotten.

### Memory Index Entry

```json
{
  "id": "memory_conv_20260118_143022",
  "entity_type": "memory",
  "source": "conversation",

  "structured": {
    "conversation_id": "conv_abc123",
    "timestamp": "2026-01-18T14:30:22Z",
    "turn_number": 5,
    "user_message": "The insurance renewal deadline is actually Feb 15, not Jan 31",
    "sage_response": "Got it - I've updated the insurance renewal deadline to February 15th..."
  },

  "analyzed": {
    "memory_type": "fact_correction",
    "importance": "high",
    "entities_mentioned": ["insurance renewal", "Brad Brezina"],
    "facts_extracted": [
      {
        "fact": "Insurance renewal deadline is February 15, 2026",
        "confidence": 1.0,
        "supersedes": "Insurance renewal deadline is January 31, 2026"
      }
    ],
    "decisions_made": [],
    "preferences_expressed": [],
    "tasks_created": [],
    "context_keywords": ["insurance", "deadline", "renewal", "february"]
  },

  "relationships": {
    "conversation_id": "conv_abc123",
    "related_contacts": ["contact_brad_brezina"],
    "related_projects": ["project_insurance_renewal"],
    "previous_memory": "memory_conv_20260118_142855",
    "superseded_facts": ["memory_conv_20260115_091200"]
  },

  "embeddings": {
    "qdrant_id": "vec_memory_conv_20260118_143022",
    "embedded_text": "Insurance renewal deadline is February 15, not January 31...",
    "embedding_model": "all-MiniLM-L6-v2"
  }
}
```

### Memory Types

| Type | Description | Example |
|------|-------------|---------|
| `fact` | New information learned | "Luke's birthday is February 13" |
| `fact_correction` | Updates existing knowledge | "Deadline changed from Jan 31 to Feb 15" |
| `decision` | Choice made by Dave | "Use Sterling Seacrest for insurance" |
| `preference` | User preference expressed | "Don't schedule meetings before 9am" |
| `task` | Something to do or remember | "Review Q4 investor update by Monday" |
| `context` | Situational information | "Meeting with Steve went well" |

### Memory Retrieval by Search Agent

When any agent requests context, the Search Agent automatically includes relevant memories:
- Semantic search against memory embeddings
- Recent conversation context (last 24 hours)
- Explicit fact lookups when entities are mentioned
- Supersession-aware (newer facts override older ones)

### Memory Conflict Resolution

When a new fact contradicts existing memory:
1. Indexer marks old fact as `superseded`
2. New fact includes `supersedes` reference
3. Search Agent only returns current (non-superseded) facts
4. Superseded facts retained for audit trail

---

## Indexing Triggers

| Trigger | Action | Frequency |
|---------|--------|-----------|
| New email received | `index_email` | Real-time (via sync job) |
| Email sent | `index_email` + check for follow-up creation | Real-time |
| Calendar event created | `index_event` | Real-time |
| Meeting transcript available | `index_meeting` | When Fireflies processes |
| **Conversation turn** | **`index_memory`** | **Real-time (every exchange)** |
| Contact mentioned in new context | `reindex_entity` (contact) | As needed |
| Daily maintenance | Reindex stale entities, clean orphans | 2 AM daily |

---

## Data Layer Interface

All access to the Data Layer goes through defined interfaces:

```python
class DataLayerInterface:
    """Abstract interface for Data Layer access."""

    # Write operations (used by Indexer Agent)
    async def store_entity(self, entity: IndexedEntity) -> str
    async def update_entity(self, entity_id: str, updates: dict) -> bool
    async def delete_entity(self, entity_id: str) -> bool
    async def create_relationship(self, from_id: str, to_id: str, rel_type: str) -> bool

    # Read operations (used by Search Agent)
    async def get_entity(self, entity_id: str) -> IndexedEntity
    async def vector_search(self, query: str, entity_types: list, limit: int) -> list[SearchResult]
    async def structured_query(self, filters: dict, entity_type: str) -> list[IndexedEntity]
    async def get_relationships(self, entity_id: str, rel_types: list) -> list[Relationship]
```

---

## DataLayerService Implementation ✅ COMPLETE

The concrete `DataLayerService` class implements `DataLayerInterface` using a hybrid adapter approach:

```
┌─────────────────────────────────────────────────────────────┐
│                    DataLayerService                         │
│            (implements DataLayerInterface)                  │
├─────────────────────────────────────────────────────────────┤
│  Entity Adapters        │  Vector Service     │  Relationships │
│  ───────────────────    │  ─────────────────  │  ────────────  │
│  EmailAdapter           │  Multi-entity       │  entity_       │
│  ContactAdapter         │  Qdrant collection  │  relationships │
│  FollowupAdapter        │  "sage_entities"    │  table         │
│  MeetingAdapter         │                     │                │
│  GenericAdapter         │                     │                │
└─────────────────────────────────────────────────────────────┘
         │                        │                    │
         ▼                        ▼                    ▼
   PostgreSQL              Qdrant                PostgreSQL
   (existing models)       (sage_entities)       (relationships)
```

**Key Design:**
- Preserves existing SQLAlchemy models (EmailCache, Contact, Followup, MeetingNote)
- Uses adapters to convert between models and `IndexedEntity`
- New `indexed_entities` table for generic types (memory, event, fact)
- New `entity_relationships` table for relationship storage
- Single Qdrant collection `sage_entities` with entity_type filtering

### Entity ID Format

| Type | Format | Example |
|------|--------|---------|
| email | `email_{gmail_id}` | `email_18d9a7b3f2c1e4d5` |
| contact | `contact_{db_id}` | `contact_42` |
| followup | `followup_{db_id}` | `followup_127` |
| meeting | `meeting_{fireflies_id}` | `meeting_ff_abc123` |
| memory | `memory_{uuid}` | `memory_550e8400...` |
| event | `event_{calendar_id}` | `event_abc123xyz` |
| fact | `fact_{uuid}` | `fact_550e8400...` |

**Location:** `sage/backend/sage/services/data_layer/`

---

## Meeting Review Service ✅ COMPLETE

The `MeetingReviewService` extracts action items from meeting transcripts and recordings using AI.

```
┌─────────────────────────────────────────────────────────────┐
│                  MeetingReviewService                       │
│           (sage/services/meeting_reviewer.py)               │
├─────────────────────────────────────────────────────────────┤
│  Sources                │  AI Extraction     │  Outputs     │
│  ───────────────────    │  ─────────────────  │  ────────── │
│  Fireflies transcripts  │  Claude Sonnet 4   │  TodoItem    │
│  Plaud recordings       │  JSON extraction   │  Followup    │
│  (via email cache)      │  Type classification│             │
└─────────────────────────────────────────────────────────────┘
```

### Action Item Types

| Type | Description | Creates |
|------|-------------|---------|
| `TODO_FOR_DAVE` | Dave committed to do something | TodoItem |
| `FOLLOWUP_EXPECTED` | Dave waiting on someone else | Followup |
| `TODO_FOR_OTHER` | Someone else committed to do something | Followup |
| `INFO_ONLY` | Mentioned but not actionable | (skipped) |

### API Endpoints

- `POST /api/v1/meetings/review/all` - Review all meetings from last N days
- `POST /api/v1/meetings/review/{meeting_id}` - Review single Fireflies meeting
- `POST /api/v1/meetings/review/plaud/{recording_id}` - Review single Plaud recording

**CLI Script:** `scripts/run_meeting_review.py`

**Initial Data:** 30-day review populated 46 todos and 82 followups

---

*Continue to [02-sub-agents.md](02-sub-agents.md) for Sub-Agent specifications.*
