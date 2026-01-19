# Sage Implementation Roadmap
## Session-by-Session Progress Tracker

**Last Updated:** January 18, 2026
**Current Phase:** Agent Infrastructure (Phase 2)
**Next Session Focus:** Write Unit Tests & Implement DataLayerInterface

---

## Quick Status

| Component | Status | Progress |
|-----------|--------|----------|
| Architecture Design | **COMPLETE** | 100% |
| Data Layer (existing) | OPERATIONAL | 80% |
| Agent Infrastructure | **IN PROGRESS** | 90% |
| Indexer Agent | STUBBED | 10% |
| Search Agent | STUBBED | 10% |
| Sage Orchestrator | STUBBED | 10% |
| Task Agents (8) | STUBBED | 15% |
| Unit Tests (base) | **COMPLETE** | 100% |
| Frontend Dashboard | PARTIAL | 60% |

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

### Phase 2: Agent Infrastructure ⏳ IN PROGRESS
- [x] Create `agents/` directory structure
- [x] Implement `BaseAgent` class
- [x] Implement `AgentResult` and `SearchContext` schemas
- [x] Implement `DataLayerInterface` (abstract interface)
- [x] Write unit tests for base classes (40 tests passing)
- [ ] Implement `DataLayerInterface` (concrete implementation)

### Phase 3: Foundational Agents
- [ ] Implement `IndexerAgent`
  - [ ] Email indexing (refactor from existing)
  - [ ] Conversation memory indexing
  - [ ] Fact extraction
  - [ ] Supersession handling
- [ ] Implement `SearchAgent`
  - [ ] Semantic search (refactor from existing)
  - [ ] Task-based context retrieval
  - [ ] Agent-specific enrichment
  - [ ] Memory retrieval

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
1. Implement concrete `DataLayerInterface` in `services/data_layer.py`
2. Implement one foundational agent end-to-end (recommend SearchAgent)
3. Wire SearchAgent to existing vector_search.py service
4. Add integration tests for SearchAgent with real Qdrant

---

## Detailed Task Backlog

### Priority 1: Agent Infrastructure
```
sage/backend/sage/agents/
├── __init__.py
├── base.py                 # BaseAgent, AgentResult, SearchContext
├── orchestrator.py         # SageOrchestrator (Phase 4)
├── foundational/
│   ├── __init__.py
│   ├── indexer.py         # IndexerAgent
│   └── search.py          # SearchAgent
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

### Priority 2: Database Schema Updates
- [ ] Add `memories` table for conversation memory
- [ ] Add `facts` table for extracted facts
- [ ] Add `superseded_by` column for fact tracking
- [ ] Create Alembic migration

### Priority 3: Refactoring Map
| Existing File | Extract To | Notes |
|---------------|------------|-------|
| `core/claude_agent.py` | `agents/task/email.py`, `agents/task/draft.py` | Split by capability |
| `core/followup_tracker.py` | `agents/task/followup.py` | Direct migration |
| `core/briefing_generator.py` | `agents/task/briefing.py` | Direct migration |
| `services/vector_search.py` | `agents/foundational/search.py` | Wrap in SearchAgent |
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
│                    LAYER 2: SUB-AGENTS                               │
│  Email | Follow-Up | Meeting | Calendar | Briefing | Draft | ...    │
│                    ┌──────────────────────┐                         │
│                    │    SEARCH AGENT      │                         │
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
| [sage-agent-architecture.md](sage-agent-architecture.md) | How Sage is built, agent specs, data schemas |
| [Backend README](sage/README.md) | Quick start, development commands |
| [API Docs](http://localhost:8000/docs) | Live API documentation (when running) |

---

## Notes & Parking Lot

*Items to consider but not currently prioritized:*

- Voice profile training from sent folder analysis
- Entrata report parsing for property metrics
- Stock price integration (Alpha Vantage API)
- Family calendar sports schedule parsing
- Mobile-responsive frontend improvements
- Webhook support for external integrations
- Multi-user support (currently single-user)

---

*This document is the source of truth for implementation progress. Update it at the end of every session.*
