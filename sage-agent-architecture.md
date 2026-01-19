# Sage Agent Architecture
## Three-Layer Multi-Agent System Design

**Version:** 1.1
**Created:** January 2026
**Last Updated:** January 18, 2026
**Status:** Implementation In Progress

---

## Executive Summary

Sage is architected as a three-layer multi-agent system:

1. **Data Layer** — Unified storage and indexing for all information
2. **Sub-Agent Layer** — Specialized agents that perform discrete tasks
3. **Orchestrator Layer** — Sage manages agents and maintains user conversation

Two foundational agents bridge the layers:
- **Indexer Agent** — Ingests and optimizes data for retrieval
- **Search Agent** — Retrieves relevant context for any sub-agent task

```
┌─────────────────────────────────────────────────────────────────────┐
│                         USER INTERFACE                               │
│                    (Chat, Dashboard, API)                            │
└─────────────────────────────────┬───────────────────────────────────┘
                                  │
┌─────────────────────────────────▼───────────────────────────────────┐
│                                                                      │
│                      LAYER 3: SAGE ORCHESTRATOR                      │
│                                                                      │
│   • Interprets user intent                                          │
│   • Routes to appropriate sub-agents                                │
│   • Aggregates results                                              │
│   • Maintains conversation context                                  │
│   • Enforces human-in-the-loop policies                            │
│                                                                      │
└─────────────────────────────────┬───────────────────────────────────┘
                                  │
┌─────────────────────────────────▼───────────────────────────────────┐
│                                                                      │
│                      LAYER 2: SUB-AGENTS                            │
│                                                                      │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐  │
│  │  Email   │ │ Follow-Up│ │ Meeting  │ │ Calendar │ │ Briefing │  │
│  │  Agent   │ │  Agent   │ │  Agent   │ │  Agent   │ │  Agent   │  │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘ └──────────┘  │
│                                                                      │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐                            │
│  │ Property │ │  Draft   │ │ Research │  ... (extensible)          │
│  │  Agent   │ │  Agent   │ │  Agent   │                            │
│  └──────────┘ └──────────┘ └──────────┘                            │
│                                                                      │
│         ┌─────────────────────────────────────────┐                 │
│         │           SEARCH AGENT                   │                 │
│         │   (retrieves context for all agents)     │                 │
│         └─────────────────────────────────────────┘                 │
│                                                                      │
└─────────────────────────────────┬───────────────────────────────────┘
                                  │
┌─────────────────────────────────▼───────────────────────────────────┐
│                                                                      │
│                       LAYER 1: DATA LAYER                           │
│                                                                      │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                     INDEXER AGENT                            │   │
│  │        (ingests, transforms, optimizes for search)           │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                      │
│  ┌───────────────┐  ┌───────────────┐  ┌───────────────┐          │
│  │  PostgreSQL   │  │    Qdrant     │  │    Redis      │          │
│  │  (structured) │  │  (vectors)    │  │   (cache)     │          │
│  └───────────────┘  └───────────────┘  └───────────────┘          │
│                                                                      │
│  ┌───────────────┐  ┌───────────────┐  ┌───────────────┐          │
│  │    Gmail      │  │   Calendar    │  │  Fireflies    │          │
│  │     API       │  │     API       │  │     API       │          │
│  └───────────────┘  └───────────────┘  └───────────────┘          │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Table of Contents

1. [Design Principles](#1-design-principles)
2. [Layer 1: Data Layer](#2-layer-1-data-layer)
3. [Layer 2: Sub-Agent Layer](#3-layer-2-sub-agent-layer)
4. [Layer 3: Sage Orchestrator](#4-layer-3-sage-orchestrator)
5. [Agent Communication Protocol](#5-agent-communication-protocol)
6. [Data Flow Examples](#6-data-flow-examples)
7. [Implementation Guide](#7-implementation-guide)
8. [Migration Path](#8-migration-path)

---

## 1. Design Principles

### 1.1 Core Tenets

1. **Separation of Concerns** — Each agent has a single, well-defined responsibility
2. **Context is King** — The Search Agent provides rich context before any agent acts
3. **Human-in-the-Loop** — No external actions without explicit approval
4. **Graceful Degradation** — If one agent fails, others continue functioning
5. **Observability** — All agent decisions and actions are logged and traceable

### 1.2 Agent Design Rules

| Rule | Description |
|------|-------------|
| Single Responsibility | Each agent does ONE thing well |
| Stateless Execution | Agents don't maintain state between invocations; state lives in Data Layer |
| Context via Search | Agents request context from Search Agent, not directly from databases |
| Structured Output | Agents return typed, predictable results |
| Explicit Capabilities | Each agent declares what it can and cannot do |

### 1.3 Information Flow

```
User Query
    │
    ▼
Sage Orchestrator
    │
    ├──► Analyzes intent
    │
    ├──► Calls Search Agent for context
    │         │
    │         ▼
    │    Data Layer (retrieval)
    │         │
    │         ▼
    │    Returns: relevant emails, contacts, history, etc.
    │
    ├──► Routes to Sub-Agent(s) with context
    │         │
    │         ▼
    │    Sub-Agent executes task
    │         │
    │         ▼
    │    Returns: result + any data to persist
    │
    ├──► (Optional) Calls Indexer Agent to persist new data
    │
    └──► Formats response for user
```

---

## 2. Layer 1: Data Layer

The Data Layer is the foundation—a unified, search-optimized repository of all information Sage knows.

### 2.1 Storage Components

| Component | Purpose | Data Types |
|-----------|---------|------------|
| **PostgreSQL** | Structured data, relationships, transactions | Users, contacts, follow-ups, emails (metadata), meetings, properties |
| **Qdrant** | Vector embeddings for semantic search | Email content, meeting transcripts, documents, notes |
| **Redis** | Caching, session state, rate limiting | Recent queries, agent results, user sessions |
| **External APIs** | Live data sources | Gmail, Google Calendar, Fireflies, Entrata |

### 2.2 The Indexer Agent

The Indexer Agent is responsible for ingesting data from all sources and preparing it for optimal retrieval.

#### Purpose
Transform raw data into search-optimized formats across all storage systems.

#### Responsibilities

1. **Ingest** — Pull data from external APIs (Gmail, Calendar, Fireflies)
2. **Transform** — Normalize, clean, and enrich data
3. **Embed** — Generate vector embeddings for semantic search
4. **Index** — Store in appropriate systems with proper metadata
5. **Link** — Create relationships between entities (email ↔ contact ↔ follow-up)
6. **Maintain** — Update stale data, remove duplicates, handle deletions

#### Indexer Agent Specification

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

#### Index Schema Design

**Email Index Entry:**
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

**Contact Index Entry:**
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

#### Conversation Memory

The Indexer Agent automatically captures and indexes conversations with Sage. This ensures nothing discussed is ever forgotten.

**Memory Index Entry:**
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
    "memory_type": "fact_correction",  // fact, decision, preference, task, correction
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

**Memory Types:**

| Type | Description | Example |
|------|-------------|---------|
| `fact` | New information learned | "Luke's birthday is February 13" |
| `fact_correction` | Updates existing knowledge | "Deadline changed from Jan 31 to Feb 15" |
| `decision` | Choice made by Dave | "Use Sterling Seacrest for insurance" |
| `preference` | User preference expressed | "Don't schedule meetings before 9am" |
| `task` | Something to do or remember | "Review Q4 investor update by Monday" |
| `context` | Situational information | "Meeting with Steve went well" |

**Memory Retrieval by Search Agent:**

When any agent requests context, the Search Agent automatically includes relevant memories:
- Semantic search against memory embeddings
- Recent conversation context (last 24 hours)
- Explicit fact lookups when entities are mentioned
- Supersession-aware (newer facts override older ones)

**Memory Conflict Resolution:**

When a new fact contradicts existing memory:
1. Indexer marks old fact as `superseded`
2. New fact includes `supersedes` reference
3. Search Agent only returns current (non-superseded) facts
4. Superseded facts retained for audit trail

#### Indexing Triggers

| Trigger | Action | Frequency |
|---------|--------|-----------|
| New email received | `index_email` | Real-time (via sync job) |
| Email sent | `index_email` + check for follow-up creation | Real-time |
| Calendar event created | `index_event` | Real-time |
| Meeting transcript available | `index_meeting` | When Fireflies processes |
| **Conversation turn** | **`index_memory`** | **Real-time (every exchange)** |
| Contact mentioned in new context | `reindex_entity` (contact) | As needed |
| Daily maintenance | Reindex stale entities, clean orphans | 2 AM daily |

### 2.3 Data Layer Interface

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

### 2.4 DataLayerService Implementation ✅ COMPLETE

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

**Entity ID Format:**
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

## 3. Layer 2: Sub-Agent Layer

Sub-agents are specialized workers that perform discrete tasks. They receive context from the Search Agent and return structured results.

### 3.1 The Search Agent

The Search Agent is the bridge between sub-agents and the Data Layer. No sub-agent queries the database directly—they request context through Search Agent.

#### Purpose
Retrieve all relevant information a sub-agent needs to perform its task.

#### Why a Dedicated Search Agent?

1. **Consistency** — All agents get context the same way
2. **Optimization** — Search logic centralized and tunable
3. **Context Quality** — Single place to improve retrieval relevance
4. **Observability** — Easy to see what context each agent received
5. **Caching** — Common queries cached efficiently

#### Search Agent Specification

```yaml
agent:
  name: search
  type: foundational
  layer: sub-agent

capabilities:
  - search_for_task      # Primary: Get everything needed for a specific task
  - semantic_search      # Find similar content by meaning
  - entity_lookup        # Get specific entity by ID
  - relationship_traverse # Follow relationships from an entity
  - temporal_search      # Find entities by time range
  - aggregate_context    # Combine multiple searches into unified context

inputs:
  - requesting_agent: str      # Which agent is asking
  - task_description: str      # What the agent is trying to do
  - entity_hints: list[str]    # Known entity IDs to include
  - time_range: tuple          # Optional date bounds
  - max_context_tokens: int    # Limit context size

outputs:
  - context: SearchContext
    - relevant_emails: list[EmailSummary]
    - relevant_contacts: list[ContactSummary]
    - relevant_meetings: list[MeetingSummary]
    - relevant_followups: list[FollowupSummary]
    - relevant_events: list[EventSummary]
    - relationship_graph: dict
    - temporal_context: str    # "What happened recently" summary
  - search_metadata: dict
    - queries_executed: int
    - entities_retrieved: int
    - context_tokens: int
```

#### Search Strategies

**Task-Based Context Retrieval:**
```python
async def search_for_task(
    self,
    requesting_agent: str,
    task_description: str,
    entity_hints: list[str] = None
) -> SearchContext:
    """
    Build comprehensive context for an agent task.

    Example: Follow-Up Agent checking overdue items
    - Get all pending/overdue follow-ups
    - For each, get related emails and contact info
    - Get any calendar events with those contacts
    - Summarize recent interaction history
    """

    context = SearchContext()

    # 1. Semantic search based on task description
    semantic_results = await self.semantic_search(
        query=task_description,
        entity_types=["email", "meeting", "note"],
        limit=20
    )

    # 2. If entity hints provided, fetch those directly
    if entity_hints:
        for entity_id in entity_hints:
            entity = await self.entity_lookup(entity_id)
            context.add_entity(entity)

            # Traverse relationships
            related = await self.relationship_traverse(
                entity_id,
                rel_types=["contact", "thread", "followup"]
            )
            context.add_related(related)

    # 3. Agent-specific context enrichment
    if requesting_agent == "followup":
        context.relevant_followups = await self.get_followups(
            statuses=["pending", "reminded", "escalated"]
        )
    elif requesting_agent == "meeting":
        context.relevant_events = await self.get_upcoming_events(days=7)

    # 4. Always include temporal context
    context.temporal_context = await self.summarize_recent_activity(days=7)

    return context
```

### 3.2 Task-Specific Sub-Agents

Each sub-agent has a focused responsibility and well-defined interface.

#### Email Agent

```yaml
agent:
  name: email
  type: task
  layer: sub-agent

description: |
  Analyzes emails, drafts replies, categorizes messages, and identifies
  emails requiring action. Does NOT send emails—only drafts.

capabilities:
  - analyze_email        # Categorize, summarize, extract action items
  - draft_reply          # Write a response in Dave's voice
  - draft_new            # Compose new email
  - categorize_batch     # Bulk categorization
  - find_related         # Find emails related to a topic/thread
  - summarize_thread     # Summarize email conversation

requires_context:
  - Email content and metadata
  - Sender's contact profile
  - Thread history
  - Any related follow-ups
  - Dave's communication style guide

outputs:
  - For analyze_email:
      category: str
      priority: str
      summary: str
      action_items: list[str]
      requires_response: bool
      suggested_response_date: date

  - For draft_reply:
      subject: str
      body: str
      to: list[str]
      cc: list[str]
      confidence: float
      notes_for_dave: str  # Any clarifications needed

human_approval_required:
  - draft_reply (before sending)
  - draft_new (before sending)
```

#### Follow-Up Agent

```yaml
agent:
  name: followup
  type: task
  layer: sub-agent

description: |
  Tracks commitments, manages reminders, identifies overdue items,
  and drafts follow-up messages. The guardian against dropped balls.

capabilities:
  - detect_followup      # Analyze sent email for follow-up need
  - check_overdue        # Find all overdue follow-ups
  - generate_reminder    # Draft Day 2 reminder
  - generate_escalation  # Draft Day 7 escalation with supervisor
  - check_resolution     # Determine if reply resolves follow-up
  - summarize_open_loops # List all open items for a contact/project

requires_context:
  - Original email that created follow-up
  - All replies in thread
  - Contact profile (including supervisor for escalation)
  - Current follow-up state
  - Related follow-ups with same contact

outputs:
  - For detect_followup:
      needs_followup: bool
      reason: str
      suggested_due_date: date
      escalation_contact: str

  - For generate_reminder:
      draft_subject: str
      draft_body: str
      to: list[str]
      cc: list[str]
      tone: str  # "gentle", "firm", "escalation"

  - For check_resolution:
      is_resolved: bool
      resolution_summary: str
      remaining_items: list[str]

human_approval_required:
  - generate_reminder (before sending)
  - generate_escalation (before sending)
```

#### Meeting Agent

```yaml
agent:
  name: meeting
  type: task
  layer: sub-agent

description: |
  Prepares context for upcoming meetings, extracts action items from
  past meetings, and helps with meeting-related tasks.

capabilities:
  - prepare_meeting      # Generate pre-meeting brief
  - extract_actions      # Pull action items from transcript
  - summarize_meeting    # Create meeting summary
  - find_history         # Get past meetings with attendees
  - suggest_topics       # Recommend discussion points

requires_context:
  - Calendar event details
  - Attendee contact profiles
  - Recent emails with attendees
  - Past meeting transcripts with attendees
  - Open follow-ups involving attendees
  - Ongoing agenda document (if exists)

outputs:
  - For prepare_meeting:
      attendees: list[AttendeeContext]
      open_items: list[str]
      recent_email_summary: str
      past_meeting_notes: str
      suggested_topics: list[str]
      relevant_documents: list[str]

  - For extract_actions:
      action_items: list[ActionItem]
      decisions_made: list[str]
      follow_ups_needed: list[FollowUpSuggestion]
```

#### Calendar Agent

```yaml
agent:
  name: calendar
  type: task
  layer: sub-agent

description: |
  Manages calendar queries, detects conflicts, coordinates with
  family schedules, and helps with scheduling decisions.

capabilities:
  - get_schedule         # Retrieve events for time range
  - detect_conflicts     # Find overlapping commitments
  - check_availability   # Find open slots
  - family_coordination  # Check family calendar impacts
  - suggest_times        # Recommend meeting times

requires_context:
  - Dave's calendar events
  - Family calendar events
  - Contact availability preferences
  - Travel time considerations
  - Kids' sports schedules

outputs:
  - For get_schedule:
      events: list[CalendarEvent]
      conflicts: list[Conflict]
      family_events: list[FamilyEvent]

  - For detect_conflicts:
      conflicts: list[Conflict]
      suggestions: list[str]  # How to resolve
```

#### Briefing Agent

```yaml
agent:
  name: briefing
  type: task
  layer: sub-agent

description: |
  Generates daily morning briefings and weekly reviews by synthesizing
  information from all other domains.

capabilities:
  - generate_morning     # Create morning briefing
  - generate_weekly      # Create weekly review
  - generate_custom      # Create ad-hoc summary

requires_context:
  - Overnight emails (urgent, action-required)
  - Today's calendar
  - Overdue and due-today follow-ups
  - Recent meeting summaries
  - Property metrics (if available)
  - Stock prices (if available)
  - Open loops across all domains

outputs:
  - For generate_morning:
      attention_items: list[AttentionItem]  # Urgent things
      calendar_summary: list[EventSummary]
      followup_summary: FollowUpStatus
      email_highlights: list[EmailHighlight]
      priorities: list[str]
      productivity_suggestion: str
```

#### Draft Agent

```yaml
agent:
  name: draft
  type: task
  layer: sub-agent

description: |
  Specializes in writing content in Dave's voice—emails, messages,
  documents. Understands Dave's communication style deeply.

capabilities:
  - draft_email          # Write email in Dave's voice
  - draft_message        # Write short message (text, Slack, etc.)
  - revise_draft         # Improve existing draft
  - adapt_tone           # Adjust formality/tone of content

requires_context:
  - Dave's voice profile
  - Recipient context
  - Purpose of communication
  - Any previous drafts/revisions
  - Examples from sent folder

outputs:
  - For draft_email:
      subject: str
      body: str
      tone_used: str
      confidence: float
      alternative_phrasings: list[str]

voice_profile:
  tone: "professional, warm, direct"
  formality: 7/10
  greetings: ["Hi [First Name],", "[First Name],"]
  closings: ["[signature block only]"]
  avoids: ["excessive exclamation points", "emojis", "hope this finds you well"]
  paragraph_style: "concise, 2-3 sentences typical"
```

#### Property Agent

```yaml
agent:
  name: property
  type: task
  layer: sub-agent

description: |
  Handles property-specific queries for Park Place and The Chateau—
  occupancy, metrics, issues, competitor analysis.

capabilities:
  - get_metrics          # Current occupancy, delinquency, etc.
  - analyze_trend        # Trend analysis over time
  - compare_competitors  # Competitor pricing analysis
  - summarize_issues     # Current property issues
  - deadline_check       # Critical deadline status

requires_context:
  - Latest Entrata reports
  - Property profiles
  - Historical metrics
  - Competitor pricing data
  - Active issues and vendor contacts
  - Critical deadlines (loan maturity, DSCR tests)

outputs:
  - For get_metrics:
      property: str
      occupancy: OccupancyData
      delinquency: float
      work_orders: WorkOrderSummary
      traffic: int
      applications: int
```

#### Research Agent

```yaml
agent:
  name: research
  type: task
  layer: sub-agent

description: |
  Gathers information from external sources—web search, document
  lookup, market research. Brings outside knowledge into Sage.

capabilities:
  - web_search           # Search the internet
  - fetch_document       # Retrieve from Google Drive
  - market_research      # Real estate market info
  - competitor_lookup    # Competitor information
  - news_search          # Relevant news articles

requires_context:
  - Research question
  - Relevant entities (properties, contacts, companies)
  - Time constraints

outputs:
  - For web_search:
      results: list[SearchResult]
      summary: str
      sources: list[str]
```

### 3.3 Sub-Agent Base Interface

All sub-agents implement this common interface:

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

@dataclass
class AgentResult:
    """Standard result from any agent."""
    success: bool
    data: dict[str, Any]
    errors: list[str] = None
    warnings: list[str] = None
    confidence: float = 1.0

    # Data to persist (sent to Indexer Agent)
    entities_to_index: list[dict] = None

    # Human approval needed?
    requires_approval: bool = False
    approval_context: str = None


class BaseAgent(ABC):
    """Base class for all sub-agents."""

    name: str
    description: str
    capabilities: list[str]

    def __init__(self, search_agent: "SearchAgent", indexer_agent: "IndexerAgent"):
        self.search = search_agent
        self.indexer = indexer_agent

    @abstractmethod
    async def execute(
        self,
        capability: str,
        params: dict,
        context: "SearchContext" = None
    ) -> AgentResult:
        """
        Execute a capability with given parameters.

        If context is not provided, agent will request it from Search Agent.
        """
        pass

    async def get_context(self, task_description: str, hints: list[str] = None) -> "SearchContext":
        """Request context from Search Agent."""
        return await self.search.search_for_task(
            requesting_agent=self.name,
            task_description=task_description,
            entity_hints=hints
        )

    async def persist_data(self, entities: list[dict]) -> None:
        """Send data to Indexer Agent for persistence."""
        for entity in entities:
            await self.indexer.index_entity(entity)
```

---

## 4. Layer 3: Sage Orchestrator

The Sage Orchestrator is the "brain" that interprets user intent, coordinates sub-agents, and maintains conversation coherence.

### 4.1 Orchestrator Responsibilities

1. **Intent Recognition** — Understand what the user wants
2. **Agent Selection** — Choose which sub-agent(s) to invoke
3. **Context Coordination** — Ensure agents have what they need
4. **Result Aggregation** — Combine outputs into coherent response
5. **Conversation Management** — Maintain multi-turn context
6. **Policy Enforcement** — Apply human-in-the-loop rules
7. **Error Handling** — Gracefully handle agent failures

### 4.2 Orchestrator Specification

```yaml
orchestrator:
  name: sage
  layer: orchestrator

responsibilities:
  - Interpret user messages
  - Route to appropriate agents
  - Manage multi-agent workflows
  - Maintain conversation history
  - Enforce approval policies
  - Format responses for user

conversation_context:
  - User profile and preferences
  - Current conversation history
  - Pending approvals
  - Active multi-step workflows
  - Recent agent results cache

routing_logic:
  - Single-agent tasks: Route directly
  - Multi-agent tasks: Coordinate sequence or parallel execution
  - Ambiguous requests: Ask for clarification
  - Complex workflows: Break into steps, track progress
```

### 4.3 Orchestrator Implementation

```python
class SageOrchestrator:
    """
    The Sage Orchestrator coordinates all agent activity and
    manages user interaction.
    """

    def __init__(self):
        # Initialize agents
        self.search_agent = SearchAgent()
        self.indexer_agent = IndexerAgent()

        self.agents: dict[str, BaseAgent] = {
            "email": EmailAgent(self.search_agent, self.indexer_agent),
            "followup": FollowUpAgent(self.search_agent, self.indexer_agent),
            "meeting": MeetingAgent(self.search_agent, self.indexer_agent),
            "calendar": CalendarAgent(self.search_agent, self.indexer_agent),
            "briefing": BriefingAgent(self.search_agent, self.indexer_agent),
            "draft": DraftAgent(self.search_agent, self.indexer_agent),
            "property": PropertyAgent(self.search_agent, self.indexer_agent),
            "research": ResearchAgent(self.search_agent, self.indexer_agent),
        }

        self.conversation_history: list[Message] = []
        self.pending_approvals: list[PendingApproval] = []
        self.conversation_id: str = None  # Set per session

    async def process_message(self, user_message: str) -> OrchestratorResponse:
        """
        Main entry point for user interaction.
        """
        # 1. Add to conversation history
        self.conversation_history.append(Message(role="user", content=user_message))

        # 2. Retrieve relevant memories before processing
        memories = await self.search_agent.get_relevant_memories(
            query=user_message,
            conversation_id=self.conversation_id
        )

        # 3. Analyze intent and plan execution (with memory context)
        execution_plan = await self._plan_execution(user_message, memories)

        # 4. Execute plan (may involve multiple agents)
        results = await self._execute_plan(execution_plan)

        # 5. Aggregate results into response
        response = await self._format_response(results, execution_plan)

        # 6. Add response to history
        self.conversation_history.append(Message(role="assistant", content=response.text))

        # 7. Index this conversation turn for future memory
        await self._index_conversation_turn(user_message, response.text, results)

        return response

    async def _index_conversation_turn(
        self,
        user_message: str,
        sage_response: str,
        results: list[AgentResult]
    ) -> None:
        """
        Index the conversation exchange for persistent memory.
        Extracts facts, decisions, and preferences automatically.
        """
        await self.indexer_agent.execute(
            capability="index_memory",
            params={
                "conversation_id": self.conversation_id,
                "turn_number": len(self.conversation_history) // 2,
                "user_message": user_message,
                "sage_response": sage_response,
                "agent_results": [r.data for r in results],
                "extract_facts": True,  # Auto-extract facts/decisions/preferences
            }
        )

    async def _plan_execution(self, user_message: str) -> ExecutionPlan:
        """
        Use Claude to analyze intent and create execution plan.
        """
        planning_prompt = f"""
        Analyze this user message and create an execution plan.

        User message: {user_message}

        Available agents and their capabilities:
        {self._get_agent_descriptions()}

        Recent conversation context:
        {self._get_recent_context()}

        Respond with:
        1. Primary intent (what does user want?)
        2. Required agents (which agents needed?)
        3. Execution order (parallel or sequential?)
        4. Context requirements (what context to gather?)
        5. Clarification needed? (any ambiguity?)
        """

        plan = await self._call_claude(planning_prompt, response_format=ExecutionPlan)
        return plan

    async def _execute_plan(self, plan: ExecutionPlan) -> list[AgentResult]:
        """
        Execute the planned agent calls.
        """
        results = []

        # First, gather context via Search Agent
        context = await self.search_agent.search_for_task(
            requesting_agent="orchestrator",
            task_description=plan.primary_intent,
            entity_hints=plan.entity_hints
        )

        # Execute agents according to plan
        if plan.execution_mode == "parallel":
            # Run agents concurrently
            tasks = [
                self.agents[agent_name].execute(
                    capability=call.capability,
                    params=call.params,
                    context=context
                )
                for agent_name, call in plan.agent_calls
            ]
            results = await asyncio.gather(*tasks, return_exceptions=True)

        elif plan.execution_mode == "sequential":
            # Run agents in order, passing results forward
            for agent_name, call in plan.agent_calls:
                result = await self.agents[agent_name].execute(
                    capability=call.capability,
                    params={**call.params, "previous_results": results},
                    context=context
                )
                results.append(result)

                # If result requires indexing, do it now
                if result.entities_to_index:
                    await self.indexer_agent.index_batch(result.entities_to_index)

        return results

    async def _format_response(
        self,
        results: list[AgentResult],
        plan: ExecutionPlan
    ) -> OrchestratorResponse:
        """
        Combine agent results into user-facing response.
        """
        # Check for any pending approvals
        pending = [r for r in results if r.requires_approval]
        if pending:
            self.pending_approvals.extend([
                PendingApproval(result=r, context=plan)
                for r in pending
            ])

        # Use Claude to synthesize response
        synthesis_prompt = f"""
        Synthesize these agent results into a helpful response for Dave.

        User's original request: {plan.primary_intent}

        Agent results:
        {self._format_results_for_synthesis(results)}

        Pending approvals needed: {len(pending)}

        Guidelines:
        - Be concise and direct
        - If approval needed, clearly state what and why
        - Offer follow-up suggestions if appropriate
        """

        response_text = await self._call_claude(synthesis_prompt)

        return OrchestratorResponse(
            text=response_text,
            agent_results=results,
            pending_approvals=pending,
            suggested_followups=self._generate_followup_suggestions(results)
        )
```

### 4.4 Intent Recognition Examples

| User Says | Primary Intent | Agents Involved |
|-----------|---------------|-----------------|
| "What's on my calendar today?" | View schedule | Calendar |
| "Draft a reply to Laura's email" | Write response | Search → Email → Draft |
| "What follow-ups are overdue?" | Check commitments | Follow-Up |
| "Prepare me for my 2pm meeting" | Meeting prep | Search → Meeting → Calendar |
| "Give me my morning briefing" | Daily summary | Briefing (calls Search internally) |
| "What's Park Place occupancy?" | Property metrics | Property |
| "Why hasn't Yanet responded?" | Investigate | Search → Follow-Up → Email |
| "Help me write an investor update" | Complex draft | Search → Property → Draft |

### 4.5 Multi-Agent Workflows

Some requests require coordinated multi-agent execution:

**Example: "Prepare for my call with Steve Hinkle about the ROW dedication"**

```
1. Orchestrator analyzes: Meeting prep + specific topic

2. Search Agent gathers:
   - Steve Hinkle's contact profile
   - All emails mentioning "ROW" or "right of way"
   - Previous meetings with Steve
   - Open follow-ups with Steve
   - Park Place property context

3. Meeting Agent prepares:
   - Attendee context for Steve
   - Topic-specific history
   - Suggested discussion points

4. Follow-Up Agent checks:
   - Any pending items with Steve re: ROW
   - Last follow-up status

5. Orchestrator synthesizes:
   - Unified meeting prep document
   - Highlighted action items
   - Suggested questions to ask
```

---

## 5. Agent Communication Protocol

### 5.1 Message Format

All inter-agent communication uses a standard message format:

```python
@dataclass
class AgentMessage:
    """Standard message between agents."""

    id: str                          # Unique message ID
    timestamp: datetime              # When sent

    from_agent: str                  # Sender agent name
    to_agent: str                    # Recipient agent name

    message_type: str                # "request", "response", "notification"

    # For requests
    capability: str = None           # Capability being invoked
    params: dict = None              # Parameters for capability

    # For responses
    result: AgentResult = None       # Result of execution

    # For context passing
    context: SearchContext = None    # Shared context

    # Tracing
    correlation_id: str = None       # Links related messages
    parent_message_id: str = None    # For chained requests
```

### 5.2 Communication Patterns

**Request-Response (Synchronous):**
```
Orchestrator ──request──► Email Agent
             ◄──response──
```

**Broadcast (Async Notification):**
```
Indexer Agent ──notification──► [All agents]
              "New email indexed"
```

**Chain (Sequential Processing):**
```
Orchestrator ──► Search Agent ──► Follow-Up Agent ──► Draft Agent
             ◄────────────────────────────────────────
```

**Fan-Out/Fan-In (Parallel):**
```
                    ┌──► Email Agent ────┐
Orchestrator ───────┼──► Calendar Agent ─┼───► Orchestrator
                    └──► Follow-Up Agent─┘
```

### 5.3 Error Handling

```python
class AgentError(Exception):
    """Base exception for agent errors."""

    def __init__(
        self,
        agent: str,
        message: str,
        recoverable: bool = True,
        fallback_suggestion: str = None
    ):
        self.agent = agent
        self.message = message
        self.recoverable = recoverable
        self.fallback_suggestion = fallback_suggestion


# Orchestrator error handling
async def _execute_with_fallback(self, agent_name: str, call: AgentCall) -> AgentResult:
    try:
        return await self.agents[agent_name].execute(call.capability, call.params)
    except AgentError as e:
        if e.recoverable:
            # Log and continue with degraded response
            logger.warning(f"Agent {e.agent} failed: {e.message}")
            return AgentResult(
                success=False,
                data={},
                errors=[f"{e.agent}: {e.message}"],
                warnings=[e.fallback_suggestion] if e.fallback_suggestion else []
            )
        else:
            # Critical failure, inform user
            raise
```

---

## 6. Data Flow Examples

### 6.1 Example: New Email Arrives

```
┌─────────────────────────────────────────────────────────────────────┐
│ 1. Gmail Sync Job detects new email                                 │
└─────────────────────────────────┬───────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────┐
│ 2. Indexer Agent processes email                                    │
│    - Extracts metadata                                              │
│    - Generates embedding                                            │
│    - Analyzes: category, priority, action items                     │
│    - Links to contact, thread                                       │
│    - Stores in PostgreSQL + Qdrant                                  │
└─────────────────────────────────┬───────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────┐
│ 3. Indexer notifies Follow-Up Agent (if sent email)                 │
│    - Follow-Up Agent checks if follow-up needed                     │
│    - If yes, creates follow-up entity                               │
│    - Indexer stores follow-up                                       │
└─────────────────────────────────┬───────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────┐
│ 4. Data available for Search Agent to retrieve                      │
└─────────────────────────────────────────────────────────────────────┘
```

### 6.2 Example: User Asks "What's overdue?"

```
┌─────────────────────────────────────────────────────────────────────┐
│ User: "What follow-ups are overdue?"                                │
└─────────────────────────────────┬───────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────┐
│ Orchestrator:                                                       │
│ 1. Recognizes intent: check_overdue                                 │
│ 2. Routes to: Follow-Up Agent                                       │
└─────────────────────────────────┬───────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────┐
│ Follow-Up Agent:                                                    │
│ 1. Requests context from Search Agent                               │
│    "Get all overdue follow-ups with related contacts and emails"    │
└─────────────────────────────────┬───────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────┐
│ Search Agent:                                                       │
│ 1. Queries PostgreSQL: followups WHERE status='pending' AND         │
│    due_date < NOW()                                                 │
│ 2. For each follow-up, fetches:                                     │
│    - Related contact profile                                        │
│    - Original email                                                 │
│    - Thread history                                                 │
│ 3. Returns SearchContext with all relevant data                     │
└─────────────────────────────────┬───────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────┐
│ Follow-Up Agent:                                                    │
│ 1. Analyzes overdue items with context                              │
│ 2. Groups by severity (1 day, 2-3 days, 4-7 days, >7 days)         │
│ 3. Generates summary with recommendations                           │
│ 4. Returns AgentResult                                              │
└─────────────────────────────────┬───────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────┐
│ Orchestrator:                                                       │
│ 1. Formats result for user                                          │
│ 2. Suggests follow-up actions ("Want me to draft reminders?")       │
│ 3. Returns response                                                 │
└─────────────────────────────────┬───────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────┐
│ User sees:                                                          │
│ "You have 3 overdue follow-ups:                                     │
│  - Yanet (renderings): 5 days overdue - HIGH priority               │
│  - Steve Hinkle (ROW): 12 days overdue - HIGH priority              │
│  - Brad Brezina (insurance): 2 days overdue - MEDIUM priority       │
│                                                                     │
│  Would you like me to draft reminder emails for any of these?"      │
└─────────────────────────────────────────────────────────────────────┘
```

### 6.3 Example: Morning Briefing Generation

```
┌─────────────────────────────────────────────────────────────────────┐
│ Trigger: Scheduler fires at 6:30 AM ET                              │
└─────────────────────────────────┬───────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────┐
│ Orchestrator: Generate morning briefing                             │
│ Routes to: Briefing Agent                                           │
└─────────────────────────────────┬───────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────┐
│ Briefing Agent requests comprehensive context:                      │
│                                                                     │
│ Search Agent gathers:                                               │
│ ┌─────────────────────────────────────────────────────────────────┐ │
│ │ • Emails received since 6 PM yesterday                          │ │
│ │   - Filter: urgent or action_required                           │ │
│ │ • Today's calendar events                                       │ │
│ │   - Include attendee context                                    │ │
│ │ • Overdue follow-ups                                            │ │
│ │ • Follow-ups due today                                          │ │
│ │ • Recent meeting summaries                                      │ │
│ │ • Property metrics (if available)                               │ │
│ │ • Stock prices (if available)                                   │ │
│ └─────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────┬───────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────┐
│ Briefing Agent synthesizes:                                         │
│ 1. Attention Items (urgent things)                                  │
│ 2. Calendar Summary (today's events with context)                   │
│ 3. Follow-Up Status (overdue + due today)                          │
│ 4. Email Highlights (important overnight emails)                    │
│ 5. Priorities (AI-generated recommendations)                        │
│ 6. Productivity Suggestion                                          │
└─────────────────────────────────┬───────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────┐
│ Result: Formatted briefing ready for delivery                       │
│ (Future: Email Agent sends to inbox)                                │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 7. Implementation Guide

### 7.1 Directory Structure

```
sage/backend/sage/
├── agents/
│   ├── __init__.py
│   ├── base.py                 # BaseAgent class, AgentResult, etc.
│   ├── orchestrator.py         # SageOrchestrator
│   │
│   ├── foundational/
│   │   ├── __init__.py
│   │   ├── indexer.py          # IndexerAgent
│   │   └── search.py           # SearchAgent
│   │
│   └── task/
│       ├── __init__.py
│       ├── email.py            # EmailAgent
│       ├── followup.py         # FollowUpAgent
│       ├── meeting.py          # MeetingAgent
│       ├── calendar.py         # CalendarAgent
│       ├── briefing.py         # BriefingAgent
│       ├── draft.py            # DraftAgent
│       ├── property.py         # PropertyAgent
│       └── research.py         # ResearchAgent
│
├── schemas/
│   ├── agent.py                # AgentMessage, AgentResult, SearchContext
│   └── ...existing schemas...
│
├── services/
│   ├── data_layer.py           # DataLayerInterface implementation
│   └── ...existing services...
│
└── api/
    ├── chat.py                 # Now calls Orchestrator
    └── ...existing endpoints...
```

### 7.2 Implementation Order

**Phase 1: Foundation (Week 1-2)**
1. Define base interfaces (`BaseAgent`, `AgentResult`, `SearchContext`)
2. Implement `DataLayerInterface`
3. Build `IndexerAgent` (refactor existing indexing logic)
4. Build `SearchAgent` (refactor existing search logic)

**Phase 2: Core Agents (Week 3-4)**
1. Implement `EmailAgent` (extract from current `claude_agent.py`)
2. Implement `FollowUpAgent` (extract from current `followup_tracker.py`)
3. Implement `CalendarAgent`
4. Implement `DraftAgent`

**Phase 3: Orchestrator (Week 5-6)**
1. Build `SageOrchestrator` with intent recognition
2. Implement routing logic
3. Implement result aggregation
4. Wire up to existing chat API

**Phase 4: Remaining Agents (Week 7-8)**
1. Implement `MeetingAgent`
2. Implement `BriefingAgent`
3. Implement `PropertyAgent`
4. Implement `ResearchAgent`

**Phase 5: Polish & Testing (Week 9-10)**
1. Comprehensive testing
2. Performance optimization
3. Error handling refinement
4. Documentation

### 7.3 Code Examples

**BaseAgent Implementation:**
```python
# agents/base.py

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Optional
from datetime import datetime

@dataclass
class AgentResult:
    """Standard result from any agent execution."""
    success: bool
    data: dict[str, Any]
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    confidence: float = 1.0

    entities_to_index: list[dict] = field(default_factory=list)

    requires_approval: bool = False
    approval_type: Optional[str] = None  # "send_email", "create_event", etc.
    approval_context: Optional[dict] = None

    execution_time_ms: int = 0
    tokens_used: int = 0


@dataclass
class SearchContext:
    """Context package provided to agents by Search Agent."""
    relevant_emails: list[dict] = field(default_factory=list)
    relevant_contacts: list[dict] = field(default_factory=list)
    relevant_followups: list[dict] = field(default_factory=list)
    relevant_meetings: list[dict] = field(default_factory=list)
    relevant_events: list[dict] = field(default_factory=list)
    relevant_memories: list[dict] = field(default_factory=list)  # Conversation memories

    relationship_graph: dict = field(default_factory=dict)
    temporal_summary: str = ""

    total_tokens: int = 0
    retrieval_metadata: dict = field(default_factory=dict)

    def is_empty(self) -> bool:
        """Check if context contains any data."""
        return not any([
            self.relevant_emails, self.relevant_contacts, self.relevant_followups,
            self.relevant_meetings, self.relevant_events, self.relevant_memories,
        ])


class BaseAgent(ABC):
    """Base class for all Sage agents."""

    name: str
    description: str
    capabilities: list[str]
    agent_type: AgentType  # FOUNDATIONAL, TASK, or ORCHESTRATOR

    def __init__(
        self,
        search_agent: "SearchAgent | None" = None,
        indexer_agent: "IndexerAgent | None" = None
    ):
        self.search = search_agent
        self.indexer = indexer_agent
        self.claude_client = None  # Injected by orchestrator if needed

    @abstractmethod
    async def execute(
        self,
        capability: str,
        params: dict[str, Any],
        context: SearchContext | None = None
    ) -> AgentResult:
        """Execute a capability. Override in subclass."""
        pass

    def supports_capability(self, capability: str) -> bool:
        """Check if this agent supports a given capability."""
        return capability in self.capabilities

    async def get_context(
        self,
        task_description: str,
        hints: list[str] | None = None
    ) -> SearchContext:
        """Request context from Search Agent."""
        if self.search is None:
            return SearchContext()  # Empty context if no search agent
        return await self.search.search_for_task(
            requesting_agent=self.name,
            task_description=task_description,
            entity_hints=hints
        )

    async def persist_data(self, entities: list[dict]) -> list[str]:
        """Send entities to Indexer Agent for persistence."""
        if self.indexer is None:
            return []
        indexed_ids = []
        for entity in entities:
            entity_id = await self.indexer.index_entity(entity)
            indexed_ids.append(entity_id)
        return indexed_ids

    def _validate_capability(self, capability: str) -> None:
        """Raise ValueError if capability is not supported."""
        if not self.supports_capability(capability):
            raise ValueError(
                f"Agent '{self.name}' does not support capability '{capability}'."
            )

    def _build_prompt(self, capability: str, params: dict, context: SearchContext) -> str:
        """Build prompt for Claude. Override for customization."""
        return f"""
        You are the {self.name} agent. Your role: {self.description}

        Task: {capability}
        Parameters: {params}

        Context:
        {self._format_context(context)}

        Execute this task and return structured results.
        """

    def _format_context(self, context: SearchContext) -> str:
        """Format SearchContext for prompt inclusion."""
        parts = []
        if context.relevant_emails:
            parts.append(f"Relevant Emails ({len(context.relevant_emails)}):")
            for email in context.relevant_emails[:10]:
                parts.append(f"  - {email.get('subject')} from {email.get('from_name')}")
        # ... similar for other context types
        return "\n".join(parts)
```

**SearchAgent Implementation:**
```python
# agents/foundational/search.py

from ..base import BaseAgent, AgentResult, SearchContext
from ...services.data_layer import DataLayerInterface

class SearchAgent(BaseAgent):
    """
    The Search Agent retrieves relevant context for any sub-agent task.
    It's the bridge between agents and the Data Layer.
    """

    name = "search"
    description = "Retrieves relevant context from the Data Layer for agent tasks"
    capabilities = [
        "search_for_task",
        "semantic_search",
        "entity_lookup",
        "relationship_traverse",
        "temporal_search"
    ]

    def __init__(self, data_layer: DataLayerInterface):
        self.data_layer = data_layer
        # Search agent doesn't need search/indexer refs
        self.search = self
        self.indexer = None

    async def execute(
        self,
        capability: str,
        params: dict,
        context: SearchContext = None
    ) -> AgentResult:
        if capability == "search_for_task":
            ctx = await self.search_for_task(**params)
            return AgentResult(success=True, data={"context": ctx})
        elif capability == "semantic_search":
            results = await self.semantic_search(**params)
            return AgentResult(success=True, data={"results": results})
        # ... other capabilities

    async def search_for_task(
        self,
        requesting_agent: str,
        task_description: str,
        entity_hints: list[str] = None,
        time_range: tuple = None,
        max_context_tokens: int = 4000
    ) -> SearchContext:
        """
        Primary method: Build comprehensive context for an agent task.
        """
        context = SearchContext()

        # 1. Always do semantic search on task description
        semantic_results = await self.semantic_search(
            query=task_description,
            entity_types=["email", "meeting", "note"],
            limit=20
        )
        context.retrieval_metadata["semantic_results"] = len(semantic_results)

        # 2. Process entity hints if provided
        if entity_hints:
            for entity_id in entity_hints:
                entity = await self.data_layer.get_entity(entity_id)
                if entity:
                    self._add_to_context(context, entity)

                    # Get related entities
                    related = await self.data_layer.get_relationships(entity_id)
                    for rel in related:
                        related_entity = await self.data_layer.get_entity(rel.to_id)
                        if related_entity:
                            self._add_to_context(context, related_entity)

        # 3. Agent-specific enrichment
        await self._enrich_for_agent(context, requesting_agent, task_description)

        # 4. Time-based context
        if time_range:
            temporal = await self.temporal_search(
                start=time_range[0],
                end=time_range[1]
            )
            context.temporal_summary = self._summarize_temporal(temporal)

        # 5. Trim to token budget
        context = self._trim_to_budget(context, max_context_tokens)

        return context

    async def semantic_search(
        self,
        query: str,
        entity_types: list[str] = None,
        limit: int = 10,
        threshold: float = 0.7
    ) -> list[dict]:
        """
        Search by semantic similarity using vector embeddings.
        """
        return await self.data_layer.vector_search(
            query=query,
            entity_types=entity_types,
            limit=limit,
            threshold=threshold
        )

    async def _enrich_for_agent(
        self,
        context: SearchContext,
        agent: str,
        task: str
    ) -> None:
        """Add agent-specific context."""

        if agent == "followup":
            # Always include pending/overdue follow-ups
            followups = await self.data_layer.structured_query(
                filters={"status__in": ["pending", "reminded", "escalated"]},
                entity_type="followup"
            )
            context.relevant_followups = followups

        elif agent == "meeting":
            # Include upcoming events
            events = await self.data_layer.structured_query(
                filters={"start_time__gte": "now", "start_time__lte": "7d"},
                entity_type="event"
            )
            context.relevant_events = events

        elif agent == "briefing":
            # Include everything for briefing
            context.relevant_followups = await self.data_layer.structured_query(
                filters={"status": "pending"},
                entity_type="followup"
            )
            context.relevant_events = await self.data_layer.structured_query(
                filters={"date": "today"},
                entity_type="event"
            )
            context.relevant_emails = await self.data_layer.structured_query(
                filters={
                    "received_at__gte": "yesterday_6pm",
                    "category__in": ["urgent", "action_required"]
                },
                entity_type="email",
                limit=20
            )

    def _add_to_context(self, context: SearchContext, entity: dict) -> None:
        """Add entity to appropriate context list."""
        entity_type = entity.get("entity_type")
        if entity_type == "email":
            context.relevant_emails.append(entity)
        elif entity_type == "contact":
            context.relevant_contacts.append(entity)
        elif entity_type == "followup":
            context.relevant_followups.append(entity)
        elif entity_type == "meeting":
            context.relevant_meetings.append(entity)
        elif entity_type == "event":
            context.relevant_events.append(entity)

    def _trim_to_budget(self, context: SearchContext, max_tokens: int) -> SearchContext:
        """Trim context to fit token budget, prioritizing recency and relevance."""
        # Implementation: estimate tokens, trim least relevant items
        # This is crucial for keeping Claude prompts manageable
        return context
```

**FollowUpAgent Implementation:**
```python
# agents/task/followup.py

from ..base import BaseAgent, AgentResult, SearchContext
from datetime import datetime, timedelta

class FollowUpAgent(BaseAgent):
    """
    Tracks commitments, manages reminders, identifies overdue items.
    The guardian against dropped balls.
    """

    name = "followup"
    description = "Tracks commitments, manages reminders, and prevents dropped follow-ups"
    capabilities = [
        "detect_followup",
        "check_overdue",
        "generate_reminder",
        "generate_escalation",
        "check_resolution",
        "summarize_open_loops"
    ]

    async def execute(
        self,
        capability: str,
        params: dict,
        context: SearchContext = None
    ) -> AgentResult:

        # Get context if not provided
        if context is None:
            context = await self.get_context(
                task_description=f"Follow-up task: {capability}",
                entity_hints=params.get("entity_hints")
            )

        if capability == "detect_followup":
            return await self._detect_followup(params, context)
        elif capability == "check_overdue":
            return await self._check_overdue(params, context)
        elif capability == "generate_reminder":
            return await self._generate_reminder(params, context)
        elif capability == "generate_escalation":
            return await self._generate_escalation(params, context)
        elif capability == "check_resolution":
            return await self._check_resolution(params, context)
        else:
            return AgentResult(
                success=False,
                data={},
                errors=[f"Unknown capability: {capability}"]
            )

    async def _check_overdue(
        self,
        params: dict,
        context: SearchContext
    ) -> AgentResult:
        """Find and categorize all overdue follow-ups."""

        now = datetime.utcnow()
        overdue_items = []

        for followup in context.relevant_followups:
            due_date = followup.get("due_date")
            if due_date and due_date < now:
                days_overdue = (now - due_date).days

                # Find related contact info
                contact = next(
                    (c for c in context.relevant_contacts
                     if c["email"] == followup.get("contact_email")),
                    None
                )

                overdue_items.append({
                    "followup_id": followup["id"],
                    "subject": followup["subject"],
                    "contact_name": followup.get("contact_name"),
                    "contact_email": followup.get("contact_email"),
                    "due_date": due_date.isoformat(),
                    "days_overdue": days_overdue,
                    "severity": self._calculate_severity(days_overdue),
                    "supervisor_email": contact.get("supervisor_email") if contact else None,
                    "original_email_id": followup.get("gmail_id")
                })

        # Sort by severity (most overdue first)
        overdue_items.sort(key=lambda x: x["days_overdue"], reverse=True)

        # Group by severity
        grouped = {
            "critical": [i for i in overdue_items if i["severity"] == "critical"],
            "high": [i for i in overdue_items if i["severity"] == "high"],
            "medium": [i for i in overdue_items if i["severity"] == "medium"],
            "low": [i for i in overdue_items if i["severity"] == "low"]
        }

        return AgentResult(
            success=True,
            data={
                "total_overdue": len(overdue_items),
                "overdue_items": overdue_items,
                "grouped": grouped,
                "summary": self._generate_overdue_summary(grouped)
            }
        )

    async def _generate_reminder(
        self,
        params: dict,
        context: SearchContext
    ) -> AgentResult:
        """Generate a reminder draft for an overdue follow-up."""

        followup_id = params.get("followup_id")
        tone = params.get("tone", "gentle")  # gentle, firm, escalation

        # Find the follow-up
        followup = next(
            (f for f in context.relevant_followups if f["id"] == followup_id),
            None
        )

        if not followup:
            return AgentResult(
                success=False,
                data={},
                errors=[f"Follow-up not found: {followup_id}"]
            )

        # Find original email for context
        original_email = next(
            (e for e in context.relevant_emails
             if e.get("gmail_id") == followup.get("gmail_id")),
            None
        )

        # Find contact
        contact = next(
            (c for c in context.relevant_contacts
             if c["email"] == followup.get("contact_email")),
            None
        )

        # Use Claude to generate the reminder
        prompt = f"""
        Generate a follow-up reminder email.

        Tone: {tone}

        Original email subject: {followup.get('subject')}
        Sent to: {followup.get('contact_name')} ({followup.get('contact_email')})
        Days overdue: {params.get('days_overdue', 'unknown')}

        Original email context:
        {original_email.get('body_text', 'Not available')[:500] if original_email else 'Not available'}

        Contact info:
        - Role: {contact.get('role', 'Unknown') if contact else 'Unknown'}
        - Supervisor: {contact.get('supervisor_email', 'None') if contact else 'None'}

        Write in Dave's voice (professional, warm, direct). No emojis.
        """

        draft = await self._call_claude(prompt)

        # Determine CC list
        cc = []
        if tone == "escalation" and contact and contact.get("supervisor_email"):
            cc.append(contact["supervisor_email"])

        return AgentResult(
            success=True,
            data={
                "draft_subject": f"Re: {followup.get('subject')}",
                "draft_body": draft,
                "to": [followup.get("contact_email")],
                "cc": cc,
                "tone": tone,
                "followup_id": followup_id
            },
            requires_approval=True,
            approval_type="send_email",
            approval_context={
                "action": "Send follow-up reminder",
                "recipient": followup.get("contact_email"),
                "tone": tone
            }
        )

    def _calculate_severity(self, days_overdue: int) -> str:
        """Calculate severity based on days overdue."""
        if days_overdue >= 7:
            return "critical"
        elif days_overdue >= 4:
            return "high"
        elif days_overdue >= 2:
            return "medium"
        else:
            return "low"

    def _generate_overdue_summary(self, grouped: dict) -> str:
        """Generate human-readable summary of overdue items."""
        parts = []
        if grouped["critical"]:
            parts.append(f"{len(grouped['critical'])} critical (7+ days)")
        if grouped["high"]:
            parts.append(f"{len(grouped['high'])} high (4-6 days)")
        if grouped["medium"]:
            parts.append(f"{len(grouped['medium'])} medium (2-3 days)")
        if grouped["low"]:
            parts.append(f"{len(grouped['low'])} low (1 day)")
        return ", ".join(parts) if parts else "No overdue items"
```

---

## 8. Migration Path

### 8.1 Mapping Current Code to New Architecture

| Current File | New Location | Changes Required |
|--------------|--------------|------------------|
| `core/claude_agent.py` | Split into multiple task agents | Extract capabilities into Email, Follow-Up, Draft agents |
| `core/followup_tracker.py` | `agents/task/followup.py` | Refactor as FollowUpAgent |
| `core/briefing_generator.py` | `agents/task/briefing.py` | Refactor as BriefingAgent |
| `services/vector_search.py` | `agents/foundational/search.py` | Integrate into SearchAgent |
| `api/emails.py` indexing logic | `agents/foundational/indexer.py` | Extract into IndexerAgent |
| `api/chat.py` | Calls `SageOrchestrator` | Replace direct Claude calls with orchestrator |

### 8.2 Step-by-Step Migration

**Step 1: Create Agent Infrastructure (No Breaking Changes)**
- Create `agents/` directory structure
- Implement `BaseAgent`, `AgentResult`, `SearchContext`
- Implement `DataLayerInterface`

**Step 2: Implement Foundational Agents**
- Build `IndexerAgent` by extracting from existing sync/indexing code
- Build `SearchAgent` by wrapping existing vector search
- Test independently

**Step 3: Migrate One Task Agent at a Time**
- Start with `FollowUpAgent` (most isolated)
- Extract logic from `followup_tracker.py`
- Test via direct invocation
- Keep old code working in parallel

**Step 4: Build Orchestrator**
- Implement `SageOrchestrator` with basic routing
- Start with just FollowUpAgent integration
- Add agents incrementally

**Step 5: Update API Layer**
- Modify `chat.py` to call Orchestrator
- Keep all other endpoints working
- Add orchestrator endpoints as needed

**Step 6: Migrate Remaining Agents**
- EmailAgent, CalendarAgent, MeetingAgent, etc.
- One at a time, testing each

**Step 7: Remove Old Code**
- Once all agents working, remove old monolithic code
- Clean up unused functions

### 8.3 Rollback Strategy

During migration, maintain ability to rollback:
- Feature flag: `USE_AGENT_ARCHITECTURE=true/false`
- Keep old `claude_agent.py` functional
- A/B test new orchestrator vs old approach

---

## Appendix A: Agent Capability Reference

| Agent | Capability | Input | Output |
|-------|------------|-------|--------|
| **Indexer** | index_email | raw email data | entity_id, relationships |
| **Indexer** | index_meeting | transcript | entity_id, action_items |
| **Search** | search_for_task | agent, description | SearchContext |
| **Search** | semantic_search | query, filters | list[entity] |
| **Email** | analyze_email | email_id | category, priority, summary |
| **Email** | draft_reply | email_id, instructions | draft |
| **Follow-Up** | detect_followup | email_id | needs_followup, due_date |
| **Follow-Up** | check_overdue | - | overdue_items |
| **Follow-Up** | generate_reminder | followup_id, tone | draft |
| **Meeting** | prepare_meeting | event_id | meeting_prep |
| **Meeting** | extract_actions | meeting_id | action_items |
| **Calendar** | get_schedule | date_range | events, conflicts |
| **Calendar** | check_availability | date_range, duration | slots |
| **Briefing** | generate_morning | - | briefing |
| **Briefing** | generate_weekly | - | review |
| **Draft** | draft_email | instructions, context | draft |
| **Property** | get_metrics | property_id | metrics |
| **Research** | web_search | query | results |

---

## Appendix B: Glossary

| Term | Definition |
|------|------------|
| **Agent** | Autonomous component that performs specific tasks |
| **Orchestrator** | Master agent that coordinates sub-agents |
| **SearchContext** | Package of relevant information for agent tasks |
| **Entity** | Any indexed item (email, contact, meeting, etc.) |
| **Capability** | Specific function an agent can perform |
| **Human-in-the-Loop** | Requiring explicit approval before external actions |

---

*This architecture enables Sage to be more intelligent, maintainable, and extensible. Each agent can be improved independently, and new agents can be added without modifying existing ones.*
