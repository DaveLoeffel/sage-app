# Sage Implementation Roadmap
## Session-by-Session Progress Tracker

**Last Updated:** January 24, 2026
**Current Phase:** Context-Aware Chat (Phase 3.9) - Testing
**Next Session Focus:** Test Phase 3.9 functionality (see phase-3.9-testing-guide.md)

---

## Quick Status

| Component | Status | Progress |
|-----------|--------|----------|
| Architecture Design | **COMPLETE** | 100% |
| Data Layer (existing) | OPERATIONAL | 80% |
| Agent Infrastructure | **COMPLETE** | 100% |
| DataLayerService | **COMPLETE** | 100% |
| Indexer Agent | **COMPLETE** | 100% |
| Search Agent | **COMPLETE** | 100% |
| Historical Data Import | **COMPLETE** | 100% |
| Behavioral Analysis | **COMPLETE** | 100% |
| Voice Profile Training | **COMPLETE** | 100% |
| Follow-up Detection | **COMPLETE** | 100% |
| **Context-Aware Chat (RAG)** | ✅ FUNCTIONAL | 90% |
| Sage Orchestrator | STUBBED | 10% |
| Task Agents (10) | STUBBED | 15% |
| TodoList Agent | **COMPLETE** | 100% |
| Meeting Review Service | **COMPLETE** | 100% |
| Clarifier Agent | PLANNED | 0% |
| Unit Tests (base + data layer + search) | **COMPLETE** | 100% |
| Frontend Dashboard | PARTIAL | 75% |

---

## Implementation Phases

### Phase 1: Architecture Definition ✅ COMPLETE
- [x] Define three-layer architecture
- [x] Specify Indexer Agent responsibilities
- [x] Specify Search Agent responsibilities
- [x] Define conversation memory schema
- [x] Document all sub-agent specifications
- [x] Create sage-agent-architecture.md
- [x] Update sage-specification.md

### Phase 2: Agent Infrastructure ✅ COMPLETE
- [x] Create `agents/` directory structure
- [x] Implement `BaseAgent` class
- [x] Implement `AgentResult` and `SearchContext` schemas
- [x] Implement `DataLayerInterface` (abstract interface)
- [x] Write unit tests for base classes (40 tests passing)
- [x] Implement `DataLayerService` (concrete implementation)
- [x] Create entity adapters (email, contact, followup, meeting, generic)
- [x] Create multi-entity vector service (`sage_entities` collection)
- [x] Create database migration for `indexed_entities` and `entity_relationships`
- [x] Write unit tests for DataLayerService (21 tests passing)

### Phase 3: Foundational Agents ✅ COMPLETE
- [x] Implement `IndexerAgent` ✅ COMPLETE (Phase 3.6.5)
  - [x] Email indexing (refactor from existing)
  - [x] Conversation memory indexing
  - [x] Fact extraction
  - [x] Supersession handling
- [x] Implement `SearchAgent` ✅ COMPLETE
  - [x] Semantic search (refactor from existing)
  - [x] Task-based context retrieval (`search_for_task`)
  - [x] Agent-specific enrichment
  - [x] Memory retrieval (`get_relevant_memories`)
  - [x] Relationship traversal
  - [x] Temporal search
  - [x] Convenience methods (`get_contact_context`, `get_thread_context`)
  - [x] Unit tests (36 tests passing)

### Phase 3.5: Historical Data Import & Training 🆕 NEXT
**Goal:** Build a comprehensive email corpus for priority learning, follow-up detection, and voice training.

#### 3.5.1 Bulk Email Import
- [x] Create bulk import endpoint (`/emails/bulk-import`)
- [x] Implement tiered indexing strategy:
  - **Tier 1 - Full Corpus (50K emails):** Metadata + vector embeddings only (no AI analysis)
  - **Tier 2 - Active Window (recent 90 days):** Full AI analysis (priority, category, summary)
  - **Tier 3 - Voice Corpus (sent emails):** Style extraction for voice training
- [x] Implement pagination for Gmail API (handle 50K+ emails)
- [x] Add progress tracking/reporting for long-running import
- [x] Include INBOX, SENT, and custom labels (e.g., "Signal") in import
- [x] Test with real Gmail account
- [x] Full import completed: 80,369 emails, 0 errors
- [x] Actual time: ~8 hours for 85K emails

#### 3.5.2 Behavioral Analysis ✅ COMPLETE
- [x] Analyze response patterns:
  - Emails user replied to quickly → high priority signals
  - Emails user starred/labeled → importance indicators
  - Senders user always responds to → VIP contacts
- [x] Build VIP sender list from historical data (397 VIP contacts identified)
- [x] Extract priority keywords from acted-upon emails (100 keywords extracted)
- [x] Store behavioral insights in `indexed_entities` (type: `insight`)
- [x] Create API endpoints for behavioral analysis
- [ ] **USER REVIEW:** Review and curate VIP contacts list (397 contacts)

#### 3.5.3 Voice Profile Extraction ✅ COMPLETE
- [x] Analyze sent emails corpus for:
  - Greeting styles (formal vs casual, by recipient type)
  - Sign-off patterns
  - Vocabulary and phrase patterns
  - Formality levels by context
  - Typical email structure
- [x] Generate voice profile document
- [x] Store as reference for Draft Agent
- [x] Create API endpoint to view/update voice profile
- [x] Filter out automated emails (calendar, transcripts, etc.)

#### 3.5.4 Follow-up Pattern Detection ✅ COMPLETE
- [x] Identify threads where user sent last message with no reply
- [x] Implement hybrid heuristics + AI classification for "expects response"
- [x] Analyze typical follow-up timing patterns (business days)
- [x] Detect "waiting for response" situations in historical data (125 found)
- [x] Seed initial follow-ups from historical analysis
- [x] Add phone numbers to daily review items
- [x] Create API endpoints: `/followups/detect`, `/followups/daily-review`

### Phase 3.6: TodoList Agent Implementation ✅ COMPLETE
**Goal:** Implement agent to scan emails and meetings for action items and maintain a comprehensive todo list.

#### 3.6.1 TodoList Agent Core ✅ COMPLETE
- [x] Create `services/todo_detector.py` with full implementation
- [x] Implement `detect_todos` capability:
  - Self-reminder detection (emails to self, "Reminder:" prefix)
  - Request detection (questions, "can you", "please")
  - Commitment detection (Dave's sent emails with "I'll", "I will")
  - Meeting action detection (from Fireflies and Plaud transcripts)
- [x] Implement `list_todos` capability with grouping (due today, due this week, overdue)
- [x] Implement `complete_todo` and `snooze_todo` capabilities in model

#### 3.6.2 TodoList Database & API ✅ COMPLETE
- [x] Create Alembic migration for `todo_items` table (migration 005):
  - id, title, description, category, priority, status
  - due_date, source_type, source_id, source_summary
  - contact_name, contact_email, created_at, completed_at, snoozed_until
  - detection_confidence, detected_deadline_text
- [x] Create Pydantic schemas for TodoItem
- [x] Create API endpoints (in frontend page)

#### 3.6.3 Meeting Review Service ✅ COMPLETE
- [x] Create `services/meeting_reviewer.py` with MeetingReviewService
- [x] Implement AI-powered action item extraction from meetings
- [x] Support Fireflies meeting transcripts
- [x] Support Plaud recordings (email-based)
- [x] Classify action items by type:
  - TODO_FOR_DAVE: Dave needs to do this
  - FOLLOWUP_EXPECTED: Dave waiting on someone
  - TODO_FOR_OTHER: Someone else committed to do
- [x] Create API endpoints:
  - `POST /api/v1/meetings/review/all` - Review all meetings (last N days)
  - `POST /api/v1/meetings/review/{meeting_id}` - Review single Fireflies meeting
  - `POST /api/v1/meetings/review/plaud/{recording_id}` - Review single Plaud recording
- [x] Create CLI script `scripts/run_meeting_review.py`
- [x] Initial 30-day review completed:
  - 22 meetings reviewed (10 Fireflies, 12 Plaud)
  - 46 todos created
  - 82 follow-ups created

#### 3.6.4 Database Schema Update ✅ COMPLETE
- [x] Create migration 006 to make followups.gmail_id nullable
- [x] Add source_type and source_id columns to followups table
- [x] Support meeting-based followups (no gmail_id required)
- [x] Update Pydantic schemas to allow nullable gmail_id/thread_id
- [x] Update FollowupResponse to include source_type and source_id fields

### Phase 3.6.5: Indexer Agent Implementation ✅ COMPLETE
**Goal:** Complete the foundational Indexer Agent that handles all data ingestion into Sage's Data Layer.

**Detailed Plan:** See [indexer-agent-implementation-plan.md](indexer-agent-implementation-plan.md)

#### 3.6.5.1 Core Infrastructure ✅
- [x] Add DataLayerService and Claude imports to IndexerAgent
- [x] Implement helper methods (entity ID generation, embedding text)
- [x] Implement simple capabilities:
  - [x] `delete_entity` - Direct DataLayerService call
  - [x] `link_entities` - Create relationships via DataLayerService
  - [x] `reindex_entity` - Delete + re-index existing entity

#### 3.6.5.2 Email & Contact Indexing ✅
- [x] Implement `index_email`:
  - [x] Accept Gmail API response or EmailCache model
  - [x] Parse headers, body, metadata into IndexedEntity
  - [x] Store via DataLayerService (auto-creates embedding)
  - [x] Optional AI analysis trigger
- [x] Implement `index_contact`:
  - [x] Accept contact data dict
  - [x] Create/update via DataLayerService + ContactAdapter
  - [x] Auto-link to related emails

#### 3.6.5.3 Conversation Memory ✅
- [x] Implement `index_memory`:
  - [x] Store user_message + sage_response as memory entity
  - [x] Extract facts, decisions, preferences via Claude
  - [x] Generate embeddings for semantic retrieval
  - [x] Link to mentioned contacts/projects
- [x] Implement `extract_facts`:
  - [x] Claude prompt for structured fact extraction
  - [x] Return facts with type, confidence, entities_mentioned
  - [x] Check for contradictions with existing facts
- [x] Implement `supersede_fact`:
  - [x] Mark old fact's metadata with `superseded_by`
  - [x] Link new fact with `supersedes` reference
  - [x] Maintain audit trail

#### 3.6.5.4 Meeting & Event Indexing ✅
- [x] Implement `index_meeting`:
  - [x] Accept Fireflies transcript or raw data
  - [x] Parse participants, action items, summary
  - [x] Link to participant contacts
- [x] Implement `index_event`:
  - [x] Accept Google Calendar event data
  - [x] Parse attendees, time, location
  - [x] Link to attendee contacts
- [x] Implement `index_document` (stub for now):
  - [x] Google Drive integration (lower priority - stub created)

#### 3.6.5.5 Integration & Testing ✅
- [x] Refactor EmailProcessor to use IndexerAgent (optional parameter)
- [x] Update chat API to call `index_memory` after exchanges (background task)
- [x] Create unit tests (`tests/agents/test_indexer_agent.py`) - 35 tests passing
- [x] Integration tests (`tests/integration/test_indexer_integration.py`) - 11 tests passing

### Phase 3.9: Context-Aware Chat (RAG Integration) 🚨 CRITICAL
**Goal:** Fix hallucination issue by integrating SearchAgent into chat flow. This is a prerequisite for useful chat functionality.

**Problem:** Chat endpoint sends user messages to Claude without any context. Claude hallucinates emails, contacts, etc. because it has no real data.

**Solution:** Wire SearchAgent into chat endpoint to retrieve relevant context before calling Claude.

#### 3.9.1 Chat Context Retrieval ✅ COMPLETE
- [x] Create `get_chat_context()` helper in chat.py that calls SearchAgent
- [x] Analyze user message to determine what types of context to retrieve
- [x] Call `SearchAgent.search_for_task()` with user message as task description
- [x] Format SearchContext into prompt-friendly context string
- [x] Pass context to `ClaudeAgent.chat()`

#### 3.9.2 Context Formatting ✅ COMPLETE
- [x] Create context formatter that converts SearchContext to readable prompt text
- [x] Include relevant emails with subject, sender, date, snippet
- [x] Include relevant contacts with name, email, relationship
- [x] Include relevant follow-ups with status, due date
- [x] Include relevant memories for conversation continuity
- [x] Add clear instructions for Claude to use only provided data

#### 3.9.3 Intent-Based Context Optimization ✅ COMPLETE
- [x] Detect general queries → use balanced context retrieval (emails + followups)
- [x] Detect email-related queries → prioritize email context
- [x] Detect follow-up queries → prioritize follow-up context
- [x] Detect meeting queries → prioritize meeting/calendar context
- [x] Detect contact queries → prioritize contact context
- [x] Detect todo queries → prioritize todo/meeting context
- [x] Add entity hints extraction from user message (names, emails, subjects)

#### 3.9.4 Testing & Validation (IN PROGRESS)
- [x] Test: "Show me emails from [real contact]" returns real emails
- [x] Test: "What follow-ups are overdue?" returns actual follow-ups
- [x] Test: System says "I don't have that information" for non-existent data
- [ ] Test: "What did we discuss about [topic]?" retrieves memories
- [ ] Test: Multi-turn conversation maintains context
- [ ] Test: Intent detection for all 6 intent types
- [ ] Test: Entity hints extraction (names, emails, subjects)
- [ ] Complete testing guide: [phase-3.9-testing-guide.md](phase-3.9-testing-guide.md)

**Expected Outcome:** Chat responses are grounded in real data from the database. Users can ask about their emails, contacts, follow-ups and get accurate answers.

**Note:** This is a simplified version of the full Orchestrator (Phase 4). Once working, Phase 4 will add intent recognition, multi-agent coordination, and approval workflows.

---

### Phase 3.8: Clarifier Agent Implementation
**Goal:** Implement agent to detect ambiguous emails and draft clarifying responses.

#### 3.8.1 Clarifier Agent Core
- [ ] Create `agents/task/clarifier.py` with full implementation
- [ ] Implement `detect_ambiguity` capability:
  - Missing deadline detection ("soon", "later", no specific date)
  - Unclear ownership detection ("someone", passive voice)
  - Vague request detection ("help with", "thoughts on")
  - Incomplete information detection
- [ ] Implement ambiguity scoring (high/medium/low/clear)
- [ ] Implement `generate_questions` capability
- [ ] Implement `draft_clarification` capability (uses Draft Agent voice)
- [ ] Create unit tests for Clarifier Agent

#### 3.8.2 Clarifier Database & API
- [ ] Create Alembic migration for `ambiguous_emails` table:
  - id, email_id, ambiguity_level, triggers (JSON)
  - suggested_questions (JSON), draft_id, status
  - created_at, reviewed_at
- [ ] Create Pydantic schemas for AmbiguousEmail
- [ ] Create API endpoints:
  - `GET /api/v1/clarifier/ambiguous` - List ambiguous emails
  - `GET /api/v1/clarifier/ambiguous/{id}` - Get details
  - `POST /api/v1/clarifier/analyze/{email_id}` - Analyze specific email
  - `POST /api/v1/clarifier/draft/{email_id}` - Generate clarification draft
  - `POST /api/v1/clarifier/dismiss/{id}` - Mark as not needing clarification

#### 3.8.3 Clarifier Integration
- [ ] Integrate with Email Agent (auto-flag ambiguous on analysis)
- [ ] Integrate with Briefing Agent (include ambiguous emails needing review)
- [ ] Add Clarifier section to frontend dashboard
- [ ] Wire to email draft/send flow (human-in-the-loop)

### Phase 4: Sage Orchestrator
- [ ] Implement intent recognition
- [ ] Implement agent routing
- [ ] Implement result aggregation
- [ ] Implement conversation management
- [ ] Wire to chat API endpoint

### Phase 5: Task Agent Migration
- [ ] Migrate Follow-Up Agent (from followup_tracker.py)
- [ ] Migrate Email Agent (from claude_agent.py)
- [ ] Migrate Briefing Agent (from briefing_generator.py)
- [ ] Implement TodoList Agent (Phase 3.6) ✅ COMPLETE
- [x] Implement Indexer Agent (Phase 3.6.5) ✅ COMPLETE
- [ ] Implement Clarifier Agent (Phase 3.8)
- [ ] Implement Meeting Agent
- [ ] Implement Calendar Agent
- [ ] Implement Draft Agent
- [ ] Implement Property Agent
- [ ] Implement Research Agent

### Phase 6: Integration & Testing
- [ ] End-to-end testing
- [ ] Performance optimization
- [ ] Error handling refinement
- [ ] Documentation completion

### Phase 7: Production Readiness
- [ ] Email sending capability
- [ ] Briefing email delivery
- [ ] Meeting prep auto-delivery
- [ ] Monitoring and alerts

---

## Session Log

### Session 1: January 18, 2026
**Duration:** ~2 hours
**Focus:** Architecture Design & Documentation

**Completed:**
1. Reviewed existing codebase and sage-specification.md
2. Updated sage-specification.md to version 2.0 (implementation status)
3. Discussed three-layer architecture requirements
4. Created sage-agent-architecture.md with:
   - Three-layer system design
   - Indexer Agent specification (including conversation memory)
   - Search Agent specification
   - All 8 task agent specifications
   - Sage Orchestrator design
   - Agent communication protocol
   - Data flow examples
   - Implementation guide
   - Migration path from existing code
5. Updated sage-specification.md to version 2.1:
   - Added architecture references
   - Simplified sections 2, 4, 5 to avoid duplication
   - Updated document control
6. Created this implementation roadmap

**Key Decisions:**
- Indexer Agent will capture all conversation exchanges for persistent memory
- Search Agent is the single point of data access for all sub-agents
- Existing code will be refactored incrementally (not rewritten)
- Human-in-the-loop principle maintained for all external actions

**Files Created/Modified:**
- `sage-agent-architecture.md` (created, ~1,500 lines)
- `sage-specification.md` (updated to v2.1)
- `sage-implementation-roadmap.md` (created, this file)

**Next Session Should:**
1. Create `agents/` directory structure
2. Implement `BaseAgent`, `AgentResult`, `SearchContext` classes
3. Implement `DataLayerInterface`
4. Write initial tests

---

### Session 2: January 18, 2026
**Duration:** ~1 hour
**Focus:** Agent Infrastructure - Directory Structure, Base Classes & Unit Tests

**Completed:**
1. Created complete `agents/` directory structure:
   ```
   sage/backend/sage/agents/
   ├── __init__.py
   ├── base.py
   ├── orchestrator.py
   ├── foundational/
   │   ├── __init__.py
   │   ├── indexer.py
   │   └── search.py
   └── task/
       ├── __init__.py
       ├── briefing.py
       ├── calendar.py
       ├── draft.py
       ├── email.py
       ├── followup.py
       ├── meeting.py
       ├── property.py
       └── research.py
   ```

2. Implemented core base classes in `base.py`:
   - `AgentType` enum (FOUNDATIONAL, TASK, ORCHESTRATOR)
   - `AgentResult` dataclass with standard response structure
   - `SearchContext` dataclass for context packages
   - `IndexedEntity`, `SearchResult`, `Relationship` data classes
   - `DataLayerInterface` abstract class with read/write operations
   - `BaseAgent` abstract base class with:
     - `execute()` abstract method
     - `get_context()` convenience method
     - `persist_data()` convenience method
     - `supports_capability()` and `_validate_capability()`

3. Created `orchestrator.py` stub with:
   - `Message`, `PendingApproval`, `ExecutionPlan`, `OrchestratorResponse` dataclasses
   - `SageOrchestrator` class with `process_message()` interface
   - Approval workflow stubs (`approve_action`, `reject_action`)
   - Memory integration stubs

4. Created foundational agent stubs:
   - `IndexerAgent` with all 11 capabilities stubbed
   - `SearchAgent` with all 6 capabilities stubbed

5. Created all 8 task agent stubs:
   - `EmailAgent` (5 capabilities)
   - `FollowUpAgent` (6 capabilities)
   - `MeetingAgent` (5 capabilities)
   - `CalendarAgent` (5 capabilities)
   - `BriefingAgent` (3 capabilities)
   - `DraftAgent` (4 capabilities)
   - `PropertyAgent` (5 capabilities)
   - `ResearchAgent` (5 capabilities)

6. Created comprehensive unit tests for base classes:
   - Created `tests/agents/` directory for agent unit tests
   - Created `tests/agents/conftest.py` to isolate from database fixtures
   - Created `tests/agents/test_base.py` with 40 test cases:
     - `TestAgentResult` (7 tests) - success/failure results, confidence, approvals
     - `TestSearchContext` (6 tests) - empty context, is_empty() method, data types
     - `TestIndexedEntity` (2 tests) - minimal and full entity creation
     - `TestSearchResult` (2 tests) - result creation, match types
     - `TestRelationship` (2 tests) - relationship creation with metadata
     - `TestDataLayerInterface` (6 tests) - concrete implementation testing
     - `TestBaseAgent` (13 tests) - properties, capabilities, execute, context, persist
     - `TestAgentType` (2 tests) - enum values
   - All 40 tests passing

**Files Created:**
- `sage/backend/sage/agents/__init__.py`
- `sage/backend/sage/agents/base.py` (~280 lines)
- `sage/backend/sage/agents/orchestrator.py` (~200 lines)
- `sage/backend/sage/agents/foundational/__init__.py`
- `sage/backend/sage/agents/foundational/indexer.py` (~220 lines)
- `sage/backend/sage/agents/foundational/search.py` (~200 lines)
- `sage/backend/sage/agents/task/__init__.py`
- `sage/backend/sage/agents/task/email.py` (~130 lines)
- `sage/backend/sage/agents/task/followup.py` (~140 lines)
- `sage/backend/sage/agents/task/meeting.py` (~130 lines)
- `sage/backend/sage/agents/task/calendar.py` (~130 lines)
- `sage/backend/sage/agents/task/briefing.py` (~100 lines)
- `sage/backend/sage/agents/task/draft.py` (~150 lines)
- `sage/backend/sage/agents/task/property.py` (~150 lines)
- `sage/backend/sage/agents/task/research.py` (~120 lines)
- `sage/backend/tests/agents/__init__.py`
- `sage/backend/tests/agents/conftest.py` (~15 lines)
- `sage/backend/tests/agents/test_base.py` (~450 lines, 40 tests)

**Total:** 18 files, ~2,400 lines of code

**Key Decisions:**
- All agents follow consistent pattern from architecture doc
- Stubs use `NotImplementedError` to make incomplete implementations explicit
- Each agent file includes detailed docstrings referencing architecture doc
- Property constants (PROPERTIES, VOICE_PROFILE) embedded in agent files
- Agent unit tests isolated in `tests/agents/` with own conftest.py
- Tests use concrete mock implementations rather than patching

**Next Session Should:**
1. Implement SearchAgent using DataLayerService
2. Wire SearchAgent to existing vector_search.py patterns
3. Add integration tests for SearchAgent with real Qdrant
4. Begin Indexer Agent implementation

---

### Session 3: January 18, 2026
**Duration:** ~2 hours
**Focus:** DataLayerService Implementation

**Completed:**
1. Created complete `services/data_layer/` directory structure:
   ```
   sage/backend/sage/services/data_layer/
   ├── __init__.py
   ├── service.py              # Main DataLayerService
   ├── vector.py               # MultiEntityVectorService
   ├── adapters/
   │   ├── __init__.py
   │   ├── base.py             # BaseEntityAdapter ABC
   │   ├── email.py            # EmailAdapter
   │   ├── contact.py          # ContactAdapter
   │   ├── followup.py         # FollowupAdapter
   │   ├── meeting.py          # MeetingAdapter
   │   └── generic.py          # GenericAdapter (memory/event/fact)
   └── models/
       ├── __init__.py
       ├── indexed_entity.py   # IndexedEntityModel
       └── relationship.py     # EntityRelationship
   ```

2. Implemented database models:
   - `IndexedEntityModel` for generic types (memory, event, fact)
   - `EntityRelationship` for relationship storage
   - JSONB columns with GIN indexes for efficient querying

3. Created entity adapters:
   - `BaseEntityAdapter` abstract class defining adapter interface
   - `EmailAdapter` → converts EmailCache ↔ IndexedEntity
   - `ContactAdapter` → converts Contact ↔ IndexedEntity
   - `FollowupAdapter` → converts Followup ↔ IndexedEntity
   - `MeetingAdapter` → converts MeetingNote ↔ IndexedEntity
   - `GenericAdapter` → handles memory/event/fact via indexed_entities table

4. Created `MultiEntityVectorService`:
   - New Qdrant collection `sage_entities`
   - Supports all entity types with `entity_type` filtering
   - Methods: `index_entity()`, `search()`, `delete_entity()`
   - Automatic payload indexing for entity_type field

5. Implemented `DataLayerService`:
   - All 8 methods from `DataLayerInterface`:
     - Write: `store_entity`, `update_entity`, `delete_entity`, `create_relationship`
     - Read: `get_entity`, `vector_search`, `structured_query`, `get_relationships`
   - Routes to appropriate adapter based on entity type
   - Automatic vector indexing on store/update
   - Relationship enrichment on entity retrieval

6. Created Alembic migration `004_add_data_layer_tables.py`:
   - `indexed_entities` table with GIN indexes on JSONB columns
   - `entity_relationships` table with unique constraint
   - Applied successfully to PostgreSQL

7. Created comprehensive unit tests:
   - `tests/services/test_data_layer.py` with 21 tests
   - Tests for all adapters and DataLayerService methods
   - All 21 tests passing

8. Verified Qdrant collection:
   - `sage_entities` collection created successfully
   - Status: green, ready for indexing

9. Initial commit to GitHub:
   - Repository: https://github.com/DaveLoeffel/sage-app
   - 131 files, 21,362 lines

**Files Created:**
- `sage/backend/sage/services/data_layer/__init__.py`
- `sage/backend/sage/services/data_layer/service.py` (~350 lines)
- `sage/backend/sage/services/data_layer/vector.py` (~200 lines)
- `sage/backend/sage/services/data_layer/adapters/__init__.py`
- `sage/backend/sage/services/data_layer/adapters/base.py` (~120 lines)
- `sage/backend/sage/services/data_layer/adapters/email.py` (~170 lines)
- `sage/backend/sage/services/data_layer/adapters/contact.py` (~180 lines)
- `sage/backend/sage/services/data_layer/adapters/followup.py` (~200 lines)
- `sage/backend/sage/services/data_layer/adapters/meeting.py` (~180 lines)
- `sage/backend/sage/services/data_layer/adapters/generic.py` (~200 lines)
- `sage/backend/sage/services/data_layer/models/__init__.py`
- `sage/backend/sage/services/data_layer/models/indexed_entity.py` (~70 lines)
- `sage/backend/sage/services/data_layer/models/relationship.py` (~50 lines)
- `sage/backend/alembic/versions/004_add_data_layer_tables.py` (~90 lines)
- `sage/backend/tests/services/__init__.py`
- `sage/backend/tests/services/conftest.py` (~15 lines)
- `sage/backend/tests/services/test_data_layer.py` (~450 lines)

**Total:** 17 new files, ~2,300 lines of code

**Key Design Decisions:**
- Hybrid adapter approach: existing models (EmailCache, Contact, etc.) use adapters; new types (memory, event, fact) use GenericAdapter with `indexed_entities` table
- Single Qdrant collection `sage_entities` for all entity types with filtering
- Entity ID format: `{type}_{source_id}` (e.g., `email_abc123`, `contact_42`)
- Soft delete for indexed_entities; hard delete for existing models
- Relationship table supports any-to-any entity relationships

**Next Session Should:**
1. Implement SearchAgent using DataLayerService
2. Wire SearchAgent to existing vector_search.py patterns
3. Add integration tests for SearchAgent with real Qdrant
4. Begin Indexer Agent implementation

---

### Session 4: January 19, 2026
**Duration:** ~2 hours
**Focus:** SearchAgent Implementation + Email Sync Fixes + Data Strategy

**Completed:**

1. **Fixed Email Display Issues:**
   - Changed default `unreadOnly` filter to `true` in emails page (only show unread by default)
   - Fixed "Sync" button to actually call Gmail sync API instead of just refetching cache
   - Added loading state and spinner during sync
   - Fixed email sync to update `is_unread` and `labels` for existing emails (was skipping them)
   - Cleared email database and resynced to fix stale unread counts

2. **Implemented SearchAgent (Full Implementation):**
   - `search_for_task` - Primary method for building context packages tailored to requesting agent
   - `semantic_search` - Vector similarity search with score thresholding
   - `entity_lookup` - Find entities by ID or structured filters
   - `relationship_traverse` - Follow relationships between entities with direction info
   - `temporal_search` - Query entities by time range
   - `get_relevant_memories` - Retrieve conversation memories for continuity
   - `get_contact_context` - Comprehensive contact info (emails, meetings, follow-ups)
   - `get_thread_context` - Full email thread with participants and related follow-ups
   - Agent-specific enrichment (followup agent gets pending followups, email agent gets unread, etc.)
   - Deduplication to prevent duplicate entities in context
   - Temporal summary generation

3. **Created SearchAgent Unit Tests:**
   - 36 comprehensive tests covering all capabilities
   - Mock DataLayerInterface for isolated testing
   - All tests passing

4. **Discussed Data Strategy for Training:**
   - Identified need for larger email corpus (up to 50K emails)
   - Three training goals: priority understanding, follow-up tracking, voice training
   - Designed tiered indexing strategy to avoid expensive AI analysis on all historical emails
   - Added Phase 3.5 to roadmap for Historical Data Import & Training

**Files Modified:**
- `sage/frontend/src/app/emails/page.tsx` - Fixed unread filter default, fixed sync button
- `sage/backend/sage/core/email_processor.py` - Fixed sync to update existing emails
- `sage/backend/sage/agents/foundational/search.py` - Full implementation (~700 lines)

**Files Created:**
- `sage/backend/tests/agents/test_search_agent.py` - Unit tests (~550 lines, 36 tests)

**Key Decisions:**
- SearchAgent is the single point of data access for all sub-agents (as per architecture)
- Tiered indexing for historical data: embeddings for all, AI analysis only for recent
- Voice training will analyze sent emails to build style profile
- Behavioral analysis will learn from response patterns, not just email content

**Next Session Should:**
1. Test bulk import with real Gmail account
2. Begin behavioral analysis (Phase 3.5.2)
3. Begin voice profile extraction from sent emails

---

### Session 5: January 19-20, 2026
**Duration:** ~10 hours (including 8-hour import)
**Focus:** Bulk Email Import Implementation & Execution (Phase 3.5.1)

**Completed:**

1. **Created Bulk Import Schemas:**
   - `BulkImportRequest` - configuration for import (labels, max emails, active window)
   - `BulkImportProgress` - detailed progress tracking with tier stats
   - `ImportTierStats` - per-tier statistics
   - `BulkImportResponse` - initial response with import ID

2. **Implemented BulkEmailImporter Class:**
   - Full pagination support for Gmail API (handles 85K+ emails)
   - Deduplication across INBOX, SENT, and custom labels
   - Three-tier processing:
     - Tier 1: All emails → metadata + embeddings only
     - Tier 2: Recent 90 days → full AI analysis
     - Tier 3: Sent emails → flagged for voice training
   - In-memory progress tracking
   - Cost estimation (embeddings + AI analysis)
   - Batch commits every 50 emails for performance

3. **Created API Endpoints:**
   - `POST /api/v1/emails/bulk-import` - Start bulk import
   - `GET /api/v1/emails/bulk-import/{import_id}` - Get progress
   - `GET /api/v1/emails/bulk-import` - List all imports

4. **Bug Fixes During Import:**
   - Fixed route ordering (bulk-import routes before /{email_id})
   - Fixed pagination bug that stopped fetching after 792 IDs
   - Fixed database truncation error for long subject lines (>500 chars)
   - Added error recovery to continue after individual email failures

5. **Executed Full Import:**
   - **Total emails found:** 85,517 (INBOX + SENT + Signal)
   - **New emails imported:** 80,369
   - **Skipped (existing):** 5,148
   - **Embeddings generated:** 80,369
   - **AI analyses (90-day window):** 1,200
   - **Voice corpus (sent):** 63,906
   - **Errors:** 0
   - **Duration:** ~8 hours

**Files Modified:**
- `sage/backend/sage/schemas/email.py` - Added bulk import schemas (~65 lines)
- `sage/backend/sage/core/email_processor.py` - Added BulkEmailImporter class (~400 lines)
- `sage/backend/sage/api/emails.py` - Added bulk import endpoints, fixed route order (~60 lines)

**Key Design Decisions:**
- Tiered indexing saved significant cost by only AI-analyzing recent emails
- Custom labels supported via `include_labels` parameter (e.g., "Signal")
- Field truncation prevents database errors on malformed emails
- Error recovery ensures one bad email doesn't crash entire import

**Next Session Should:**
1. Implement behavioral analysis (Phase 3.5.2)
2. Begin voice profile extraction from 63,906 sent emails
3. Detect follow-up patterns from historical data

---

### Session 6: January 20, 2026
**Duration:** ~3 hours
**Focus:** Behavioral Analysis (3.5.2) + Voice Profile (3.5.3) + Follow-up Detection (3.5.4)

**Completed:**

#### Part 1: Behavioral Analysis (Phase 3.5.2)

1. **Created BehavioralAnalyzer Service:**
   - `sage/backend/sage/services/behavioral_analyzer.py` (~450 lines)
   - Analyzes response patterns across 85K email corpus
   - Identifies VIP contacts based on response rate thresholds
   - Extracts priority keywords from quickly-responded emails
   - Analyzes starred/important label patterns

2. **Response Pattern Analysis:**
   - Correlates received emails with sent replies in same thread
   - Calculates response times per sender
   - Identifies senders with >50% response rate as VIPs
   - Found 397 VIP contacts from 1,124 unique senders

3. **Priority Keyword Extraction:**
   - Extracts words from emails that got quick responses (<4 hours)
   - Filters extensive stop word list (email boilerplate, signatures, etc.)
   - Identified 100 meaningful priority keywords

4. **Created Behavioral Analysis API:**
   - `POST /api/v1/emails/behavioral-analysis` - Run analysis
   - `GET /api/v1/emails/behavioral-analysis?user_email=` - Get insights
   - `GET /api/v1/emails/vip-contacts` - List VIP contacts

#### Part 2: Voice Profile Extraction (Phase 3.5.3)

5. **Created VoiceProfileExtractor Service:**
   - `sage/backend/sage/services/voice_profile_extractor.py` (~750 lines)
   - Analyzes sent emails to learn user's writing style
   - Filters out automated emails (calendar invites, transcripts, etc.)
   - Extracts signature patterns, greetings, sign-offs
   - Calculates formality score and style metrics

6. **Voice Profile Results:**
   - Emails analyzed: 5,000 (sampled, filters applied)
   - Greeting usage: 0.5% (rarely uses greetings)
   - Sign-off preference: "Thank you"
   - Avg email length: 95 words
   - Formality score: 0.03 (very casual)
   - Structure: direct (gets straight to the point)
   - Uses contractions: Yes

7. **Created Voice Profile API:**
   - `POST /api/v1/emails/voice-profile` - Extract profile
   - `GET /api/v1/emails/voice-profile?user_email=` - Get profile
   - Profile includes prompt guidance for Draft Agent

#### Part 3: Follow-up Pattern Detection (Phase 3.5.4)

8. **Created FollowupPatternDetector Service:**
   - `sage/backend/sage/services/followup_detector.py` (~600 lines)
   - Hybrid heuristics + AI classification for "expects response"
   - Business day timing calculation
   - Filters out calendar invites, self-emails, stale threads (>60 days)

9. **Classification System:**
   - Heuristic patterns: question marks, request phrases, deadlines (+points)
   - Closing patterns: "Thanks", "Got it", "Sounds good" (-points)
   - Ambiguous cases (score 30-60) routed to AI classification
   - All 6 test cases passing

10. **Detection Results:**
    - Threads analyzed: 1,393 (6 months)
    - Threads waiting for response: 125
    - Action breakdown: 110 call+followup, 12 send, 3 draft

11. **Created Follow-up APIs:**
    - `POST /api/v1/followups/detect` - Run detection
    - `GET /api/v1/followups/detect/{id}` - Check progress
    - `GET /api/v1/followups/daily-review` - Get items with phone numbers

**Files Created:**
- `sage/backend/sage/services/behavioral_analyzer.py` (~450 lines)
- `sage/backend/sage/services/voice_profile_extractor.py` (~750 lines)
- `sage/backend/sage/services/followup_detector.py` (~600 lines)

**Files Modified:**
- `sage/backend/sage/schemas/email.py` - Added behavioral + voice profile schemas
- `sage/backend/sage/schemas/followup.py` - Added detection schemas
- `sage/backend/sage/api/emails.py` - Added voice profile endpoints
- `sage/backend/sage/api/followups.py` - Added detection endpoints

**Key Design Decisions:**
- VIP threshold: 3+ emails received AND 50%+ response rate
- Voice profile filters out calendar/transcript noise automatically
- Profile generates prompt guidance for Draft Agent integration
- Follow-up timing: 1 day→draft, 3 days→send, 5+ days→call
- Hybrid classification: heuristics first, AI for ambiguous
- Max follow-up age: 60 business days

**Next Session Should:**
1. Begin Sage Orchestrator implementation (Phase 4)
2. Implement intent recognition and agent routing
3. Wire orchestrator to chat API

---

### Session 7: January 20, 2026
**Duration:** ~1 hour
**Focus:** SAR Documentation Updates for TodoList Agent and Clarifier Agent

**Completed:**

1. **Updated sage-specification.md (v2.3):**
   - Added TodoList Agent and Clarifier Agent to agent overview table
   - Added detailed sections (5.3, 5.4) for both new agents
   - Updated architecture diagram to show 10 task agents
   - Updated Briefing Agent to include TodoList and Clarifier integration
   - Updated morning briefing example with TodoList section and ambiguous email alerts

2. **Updated sage-agent-architecture.md (v1.2):**
   - Updated architecture diagram to include TodoList and Clarifier agents
   - Added detailed YAML specifications for both agents:
     - TodoList Agent: detect_todos, list_todos, complete_todo, snooze_todo, extract_from_meeting
     - Clarifier Agent: detect_ambiguity, generate_questions, draft_clarification, list_ambiguous
   - Added data flow examples (6.3, 6.4) for both agents
   - Updated intent recognition examples table
   - Updated capability reference table in Appendix A

3. **Updated sage-implementation-roadmap.md:**
   - Added Phase 3.6: TodoList Agent Implementation
   - Added Phase 3.7: Clarifier Agent Implementation
   - Updated Quick Status table with new agents
   - Updated Phase 5 to include new agents
   - Updated current phase and next session focus

**Key Design Decisions:**
- TodoList categories: self_reminder, request_received, commitment_made, meeting_action
- TodoList priority rules: urgent (24h deadline), high (VIP/1 week), normal, low
- Clarifier triggers: missing_deadline, unclear_ownership, vague_request, multiple_interpretations, incomplete_info
- Clarifier maintains human-in-the-loop for all draft emails
- Both agents integrate with daily briefing

**Files Modified:**
- `sage-specification.md` (v2.3)
- `sage-agent-architecture.md` (v1.2)
- `sage-implementation-roadmap.md`

**Next Session Should:**
1. Begin TodoList Agent implementation (Phase 3.6)
2. Create database migration for `todo_items` table
3. Implement `detect_todos` capability

---

### Session 8: January 20, 2026
**Duration:** ~1 hour
**Focus:** Dashboard & Calendar Improvements

**Completed:**

1. **Made Dashboard Stat Cards Clickable:**
   - Updated `StatCard` component to use Next.js `Link`
   - Added hover effects (shadow, background color)
   - Configured navigation URLs:
     - "Overdue Follow-ups" → `/followups?overdue=true`
     - "Overdue Todos" → `/todos?overdue=true`
     - "Pending Todos" → `/todos`
     - "Unread Emails" → `/emails`
     - "Completed Today" → `/todos?status=completed`

2. **Added URL Parameter Support to Filter Pages:**
   - Updated `/followups/page.tsx` to read `overdue`, `status`, `priority` from URL
   - Updated `/todos/page.tsx` to read `overdue`, `status`, `category`, `priority` from URL
   - Used `useSearchParams` hook and `useEffect` for initialization

3. **Fixed Calendar Widget in Dashboard:**
   - Dashboard API was returning empty `todays_events` array (TODO placeholder)
   - Added `get_todays_calendar_events()` helper function to dashboard API
   - Function fetches from Google Calendar using user's OAuth tokens
   - Calendar widget now displays today's events on dashboard

4. **Fixed Calendar Page Timezone Bug:**
   - Issue: Calendar showed "Today" as Jan 19th when it was Jan 20th
   - Root cause: `toISOString()` converts dates to UTC, shifting back a day for western timezones
   - Solution: Created `formatLocalDate()` helper to format dates in local timezone
   - Fixed both day header generation and event date matching
   - Fixed date display by parsing date strings with `T00:00:00` suffix

**Files Modified:**
- `sage/frontend/src/app/page.tsx` - Clickable stat cards, added Link import
- `sage/frontend/src/app/followups/page.tsx` - URL parameter support
- `sage/frontend/src/app/todos/page.tsx` - URL parameter support
- `sage/frontend/src/app/calendar/page.tsx` - Timezone fix with `formatLocalDate()`
- `sage/backend/sage/api/dashboard.py` - Calendar events integration

**Key Decisions:**
- Stat cards navigate to filtered list pages rather than opening modals
- Used URL parameters (not route params) for filter state to allow easy sharing/bookmarking
- Calendar events fetched in real-time from Google API (not cached)
- Local timezone formatting ensures dates display correctly regardless of user location

**Next Session Should:**
1. Continue Clarifier Agent implementation (Phase 3.8)
2. Or begin Sage Orchestrator implementation (Phase 4)

---

### Session 8b: January 20, 2026
**Duration:** ~30 min
**Focus:** Documentation Restructuring

**Completed:**

1. **Split Architecture Document into Focused Files:**
   - Created `sage-architecture/` directory with 6 focused documents:
     - `00-overview.md` - Executive summary, design principles, agent summary
     - `01-data-layer.md` - Data Layer, Indexer Agent, schemas, DataLayerService
     - `02-sub-agents.md` - Search Agent and all 10 task agent specifications
     - `03-orchestrator.md` - Sage Orchestrator, intent recognition, routing
     - `04-data-flow.md` - Agent communication protocol and data flow examples
     - `05-implementation.md` - Implementation guide, migration path, appendices
   - Original `sage-agent-architecture.md` now redirects to new location
   - Each document is under 25K tokens for easy reading

2. **Updated Document References:**
   - Updated `sage-implementation-roadmap.md` reference links
   - Added cross-references between split documents

**Rationale:**
- Original architecture doc exceeded 25K token limit, requiring chunked reads
- Split structure enables focused updates without loading entire document
- Each section can be maintained independently

**Files Created:**
- `sage-architecture/00-overview.md`
- `sage-architecture/01-data-layer.md`
- `sage-architecture/02-sub-agents.md`
- `sage-architecture/03-orchestrator.md`
- `sage-architecture/04-data-flow.md`
- `sage-architecture/05-implementation.md`

**Files Modified:**
- `sage-agent-architecture.md` - Now a redirect file
- `sage-implementation-roadmap.md` - Updated reference links

---

### Session 9: January 22, 2026
**Duration:** ~1.5 hours
**Focus:** Phase 3.9 - Context-Aware Chat (RAG Integration) 🚨 CRITICAL FIX

**Problem Identified:**
- Chat endpoint was sending user messages directly to Claude without any database context
- Result: Claude hallucinated fake emails, contacts, and follow-ups
- Root cause: SearchAgent (fully implemented) was never called from chat flow

**Completed:**

1. **Implemented Context-Aware Chat:**
   - Created `get_chat_context()` function in `chat.py` that calls SearchAgent
   - Created `format_search_context()` to convert SearchContext to Claude-friendly format
   - Added instructions telling Claude to only use provided data, never hallucinate
   - Wired context retrieval into chat endpoint before calling ClaudeAgent

2. **Fixed SearchAgent for Chat:**
   - Added "chat" case to `_enrich_for_agent()` method
   - Chat now gets comprehensive context: unread emails + active followups
   - Added error handling around each query type

3. **Fixed FollowupAdapter Query:**
   - Bug: Status filter didn't handle list values like `["pending", "reminded", "escalated"]`
   - Fix: Added list handling with `Followup.status.in_(enum_values)`

4. **Testing Results:**
   - ✅ "What followups are overdue?" → Returns real contacts (Antonio Ralda, Sam Sweitzer, Keri Colgrove)
   - ✅ "Show me unread emails" → Returns real emails with actual senders and subjects
   - ✅ "What did John Smith email me?" → Correctly says "I don't see any emails from John Smith"
   - ✅ No more hallucination of fake data

**Files Modified:**
- `sage/backend/sage/api/chat.py` - Added context retrieval (get_chat_context, format_search_context)
- `sage/backend/sage/agents/foundational/search.py` - Added "chat" enrichment case
- `sage/backend/sage/services/data_layer/adapters/followup.py` - Fixed list filter handling
- `sage-implementation-roadmap.md` - Added Phase 3.9, updated status
- `sage-architecture/04-data-flow.md` - Added implementation note

**Key Design Decisions:**
- Context includes up to 10 emails, 10 followups, 5 meetings, 5 memories (to limit token usage)
- Added explicit instructions for Claude: "Use ONLY this data... Never hallucinate"
- Error handling returns minimal context with warning rather than failing

**Next Session Should:**
1. Implement intent-based context optimization (prioritize based on query type)
2. Add entity hints extraction (names, subjects from user message)
3. Continue with Sage Orchestrator (Phase 4) for full multi-agent coordination

---

### Session 10: January 22, 2026
**Duration:** ~30 minutes
**Focus:** Phase 3.9.3 - Intent-Based Context Optimization

**Completed:**

1. **Implemented Intent Detection:**
   - Created `ChatIntent` enum with 6 intent types: EMAIL, FOLLOWUP, MEETING, CONTACT, TODO, GENERAL
   - Created `detect_chat_intent()` function using regex pattern matching
   - Scores messages against keyword patterns for each intent type
   - Falls back to GENERAL if no strong match

2. **Implemented Entity Hints Extraction:**
   - Created `extract_entity_hints()` function to extract search hints from messages
   - Extracts email addresses (regex pattern)
   - Extracts quoted strings (potential subjects or exact phrases)
   - Extracts potential names (capitalized word sequences)
   - Extracts "from X" and "about X" patterns
   - Filters common words to reduce noise

3. **Updated Chat Context Retrieval:**
   - `get_chat_context()` now calls `detect_chat_intent()` and `extract_entity_hints()`
   - Maps intents to agent types for SearchAgent (e.g., EMAIL → chat_email)
   - Adds intent-specific guidance to Claude's instructions
   - Logs detected intent and extracted hints for debugging

4. **Updated SearchAgent Enrichment:**
   - Added 6 new enrichment methods for intent-based context:
     - `_enrich_chat_general()` - Balanced context (original behavior)
     - `_enrich_chat_email()` - Prioritizes email data with 2x limit
     - `_enrich_chat_followup()` - Prioritizes followup data with 2x limit
     - `_enrich_chat_meeting()` - Prioritizes meeting/calendar data
     - `_enrich_chat_contact()` - Prioritizes contact and interaction history
     - `_enrich_chat_todo()` - Prioritizes meeting and followup context (todo source)
   - Updated `_enrich_for_agent()` to route to appropriate method

5. **Testing:**
   - All 36 SearchAgent unit tests passing
   - Intent detection correctly classifies 13/14 test messages (93%)
   - Entity extraction successfully extracts emails, names, and quoted phrases

**Files Modified:**
- `sage/backend/sage/api/chat.py` - Added intent detection, entity extraction (~140 lines)
- `sage/backend/sage/agents/foundational/search.py` - Added intent-based enrichment (~200 lines)
- `sage-implementation-roadmap.md` - Updated status, added session log

**Key Design Decisions:**
- Intent detection uses simple regex patterns (fast, no API calls)
- Each intent type gets prioritized context (2x limit for primary data type)
- Entity hints are passed to SearchAgent for improved semantic search
- Intent-specific guidance added to Claude's system instructions

**Next Session Should:**
1. Continue with Sage Orchestrator (Phase 4) for full multi-agent coordination
2. Or implement Clarifier Agent (Phase 3.8) for ambiguous email detection

---

## Detailed Task Backlog

### Priority 1: Historical Data Import (Phase 3.5)
```
Tiered Indexing Strategy:
┌─────────────────────────────────────────────────────────────────┐
│ Tier 1: FULL CORPUS (50K emails)                                │
│ - All inbox + sent emails                                       │
│ - Store: metadata + vector embeddings                           │
│ - Skip: AI analysis (priority, category, summary)               │
│ - Cost: ~$5-10 (embeddings only)                                │
└─────────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────▼───────────────────────────────────┐
│ Tier 2: ACTIVE WINDOW (recent 90 days, ~2K emails)              │
│ - Full AI analysis                                              │
│ - Priority, category, summary, action items                     │
│ - This is the "working set" for daily use                       │
└─────────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────▼───────────────────────────────────┐
│ Tier 3: VOICE CORPUS (all sent emails, ~5K)                     │
│ - Style extraction for voice training                           │
│ - Greeting/sign-off patterns                                    │
│ - Vocabulary and formality levels                               │
└─────────────────────────────────────────────────────────────────┘
```

### Priority 2: Agent Infrastructure
```
sage/backend/sage/agents/
├── __init__.py
├── base.py                 # BaseAgent, AgentResult, SearchContext
├── orchestrator.py         # SageOrchestrator (Phase 4)
├── foundational/
│   ├── __init__.py
│   ├── indexer.py         # IndexerAgent (needs implementation)
│   └── search.py          # SearchAgent ✅ COMPLETE
└── task/
    ├── __init__.py
    ├── email.py           # EmailAgent
    ├── followup.py        # FollowUpAgent
    ├── meeting.py         # MeetingAgent
    ├── calendar.py        # CalendarAgent
    ├── briefing.py        # BriefingAgent
    ├── draft.py           # DraftAgent
    ├── property.py        # PropertyAgent
    └── research.py        # ResearchAgent
```

### Priority 3: Database Schema Updates
- [ ] Add `memories` table for conversation memory
- [ ] Add `facts` table for extracted facts
- [ ] Add `superseded_by` column for fact tracking
- [ ] Add `voice_profile` table for writing style
- [ ] Add `behavioral_insights` table for priority patterns
- [ ] Create Alembic migration

### Priority 4: Refactoring Map
| Existing File | Extract To | Notes |
|---------------|------------|-------|
| `core/claude_agent.py` | `agents/task/email.py`, `agents/task/draft.py` | Split by capability |
| `core/followup_tracker.py` | `agents/task/followup.py` | Direct migration |
| `core/briefing_generator.py` | `agents/task/briefing.py` | Direct migration |
| `services/vector_search.py` | Used by DataLayerService | Already integrated |
| `api/emails.py` (indexing) | `agents/foundational/indexer.py` | Extract indexing logic |

---

## Architecture Quick Reference

```
┌─────────────────────────────────────────────────────────────────────┐
│                         USER INTERFACE                               │
└─────────────────────────────────┬───────────────────────────────────┘
                                  │
┌─────────────────────────────────▼───────────────────────────────────┐
│              LAYER 3: SAGE ORCHESTRATOR                              │
└─────────────────────────────────┬───────────────────────────────────┘
                                  │
┌─────────────────────────────────▼───────────────────────────────────┐
│                    LAYER 2: SUB-AGENTS (10 total)                    │
│  Email | Follow-Up | TodoList | Clarifier | Meeting | Calendar      │
│  Briefing | Draft | Property | Research                             │
│                    ┌──────────────────────┐                         │
│                    │  SEARCH AGENT ✅      │                         │
│                    └──────────────────────┘                         │
└─────────────────────────────────┬───────────────────────────────────┘
                                  │
┌─────────────────────────────────▼───────────────────────────────────┐
│                      LAYER 1: DATA LAYER                             │
│                    ┌──────────────────────┐                         │
│                    │    INDEXER AGENT     │                         │
│                    └──────────────────────┘                         │
│  PostgreSQL | Qdrant | Redis | Gmail | Calendar | Fireflies         │
└─────────────────────────────────────────────────────────────────────┘
```

---

## How to Use This Document

### At the Start of Each Session
1. Read the "Quick Status" table
2. Read the last session's log entry
3. Check "Next Session Should" items
4. Begin work on identified tasks

### At the End of Each Session
1. Update "Quick Status" table
2. Add new session log entry with:
   - What was completed
   - Key decisions made
   - Files created/modified
   - What next session should focus on
3. Update task checkboxes in Implementation Phases
4. Update "Last Updated" date at top

### When Blocked or Pivoting
1. Document the blocker in session log
2. Note any architectural decisions
3. Update affected tasks/phases

---

## Reference Links

| Document | Purpose |
|----------|---------|
| [sage-specification.md](sage-specification.md) | What Sage does, who it serves, business context |
| [sage-architecture/](sage-architecture/00-overview.md) | How Sage is built, agent specs, data schemas (split into focused docs) |
| [Backend README](sage/README.md) | Quick start, development commands |
| [API Docs](http://localhost:8000/docs) | Live API documentation (when running) |

---

## Notes & Parking Lot

*Items to consider but not currently prioritized:*

- Entrata report parsing for property metrics
- Stock price integration (Alpha Vantage API)
- Family calendar sports schedule parsing
- Mobile-responsive frontend improvements
- Webhook support for external integrations
- Multi-user support (currently single-user)

---

*This document is the source of truth for implementation progress. Update it at the end of every session.*
