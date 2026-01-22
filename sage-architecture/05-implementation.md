# Sage Agent Architecture: Implementation Guide

**Part of:** [Sage Architecture Documentation](00-overview.md)

---

## Directory Structure

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
│       ├── todolist.py         # TodoListAgent ✅
│       ├── clarifier.py        # ClarifierAgent
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
│   ├── meeting_reviewer.py     # MeetingReviewService ✅
│   ├── todo_detector.py        # TodoDetector service ✅
│   ├── followup_detector.py    # FollowupPatternDetector ✅
│   ├── behavioral_analyzer.py  # BehavioralAnalyzer service ✅
│   ├── voice_profile_extractor.py # VoiceProfileExtractor ✅
│   └── ...existing services...
│
└── api/
    ├── chat.py                 # Context-aware chat (Phase 3.9) - calls SearchAgent for RAG
    └── ...existing endpoints...
```

---

## Implementation Order

### Phase 1: Foundation (Week 1-2)
1. Define base interfaces (`BaseAgent`, `AgentResult`, `SearchContext`)
2. Implement `DataLayerInterface`
3. Build `IndexerAgent` (refactor existing indexing logic)
4. Build `SearchAgent` (refactor existing search logic)

### Phase 2: Core Agents (Week 3-4)
1. Implement `EmailAgent` (extract from current `claude_agent.py`)
2. Implement `FollowUpAgent` (extract from current `followup_tracker.py`)
3. Implement `CalendarAgent`
4. Implement `DraftAgent`

### Phase 3: Orchestrator (Week 5-6)
1. Build `SageOrchestrator` with intent recognition
2. Implement routing logic
3. Implement result aggregation
4. Wire up to existing chat API

### Phase 4: Remaining Agents (Week 7-8)
1. Implement `MeetingAgent`
2. Implement `BriefingAgent`
3. Implement `PropertyAgent`
4. Implement `ResearchAgent`

### Phase 5: Polish & Testing (Week 9-10)
1. Comprehensive testing
2. Performance optimization
3. Error handling refinement
4. Documentation

---

## Code Examples

### BaseAgent Implementation

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

### SearchAgent Implementation

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

### FollowUpAgent Implementation

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

## Migration Path

### Mapping Current Code to New Architecture

| Current File | New Location | Changes Required |
|--------------|--------------|------------------|
| `core/claude_agent.py` | Split into multiple task agents | Extract capabilities into Email, Follow-Up, Draft agents |
| `core/followup_tracker.py` | `agents/task/followup.py` | Refactor as FollowUpAgent |
| `core/briefing_generator.py` | `agents/task/briefing.py` | Refactor as BriefingAgent |
| `services/vector_search.py` | `agents/foundational/search.py` | Integrate into SearchAgent |
| `api/emails.py` indexing logic | `agents/foundational/indexer.py` | Extract into IndexerAgent |
| `api/chat.py` | Calls `SageOrchestrator` | Replace direct Claude calls with orchestrator |

### Step-by-Step Migration

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

### Rollback Strategy

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
| **TodoList** | detect_todos | email_id/batch | todos_found, duplicates |
| **TodoList** | list_todos | filters | grouped todos (due today, week, overdue) |
| **TodoList** | complete_todo | todo_id | success |
| **TodoList** | snooze_todo | todo_id, date | success |
| **TodoList** | extract_from_meeting | meeting_id | action_items for Dave |
| **Clarifier** | detect_ambiguity | email_id | is_ambiguous, triggers, questions |
| **Clarifier** | draft_clarification | email_id | draft email with questions |
| **Clarifier** | list_ambiguous | filters | ambiguous emails needing clarity |
| **Meeting** | prepare_meeting | event_id | meeting_prep |
| **Meeting** | extract_actions | meeting_id | action_items |
| **Calendar** | get_schedule | date_range | events, conflicts |
| **Calendar** | check_availability | date_range, duration | slots |
| **Briefing** | generate_morning | - | briefing (includes todos + ambiguous) |
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

---

**Back to:** [Architecture Overview](00-overview.md)
