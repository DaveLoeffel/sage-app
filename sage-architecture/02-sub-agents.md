# Sage Agent Architecture: Sub-Agents

**Part of:** [Sage Architecture Documentation](00-overview.md)

---

## Layer 2: Sub-Agent Layer

Sub-agents are specialized workers that perform discrete tasks. They receive context from the Search Agent and return structured results.

---

## The Search Agent

The Search Agent is the bridge between sub-agents and the Data Layer. No sub-agent queries the database directly—they request context through Search Agent.

### Purpose
Retrieve all relevant information a sub-agent needs to perform its task.

### Why a Dedicated Search Agent?

1. **Consistency** — All agents get context the same way
2. **Optimization** — Search logic centralized and tunable
3. **Context Quality** — Single place to improve retrieval relevance
4. **Observability** — Easy to see what context each agent received
5. **Caching** — Common queries cached efficiently

### Search Agent Specification

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

### Search Strategies

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

---

## Task-Specific Sub-Agents

Each sub-agent has a focused responsibility and well-defined interface.

### Email Agent

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

### Follow-Up Agent

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

### TodoList Agent

```yaml
agent:
  name: todolist
  type: task
  layer: sub-agent

description: |
  Scans emails for action items that Dave needs to complete. Tracks both
  self-reminders and requests from others. Integrates with daily briefing
  to ensure no task is forgotten.

capabilities:
  - detect_todos          # Scan email for action items
  - list_todos            # Get all todos with filters
  - create_todo           # Manually create a todo
  - complete_todo         # Mark todo as done
  - snooze_todo           # Postpone todo to later date
  - extract_from_meeting  # Pull action items from meeting transcript

requires_context:
  - Email content (received and sent)
  - Meeting transcripts
  - VIP contacts list (for priority assignment)
  - Existing todo items (to avoid duplicates)
  - Calendar context (for deadline detection)

detection_sources:
  - self_reminder: Emails Dave sends to himself, or contains "Reminder:"
  - request_received: Incoming emails with questions, requests, "can you"
  - commitment_made: Dave's sent emails with "I'll", "I will", "I can"
  - meeting_action: Action items assigned to Dave in meeting transcripts

todo_categories:
  - self_reminder: Dave reminding himself to do something
  - request_received: Someone explicitly asks Dave to do something
  - commitment_made: Dave promises to do something in a sent email
  - meeting_action: Action item from meeting assigned to Dave

priority_rules:
  - urgent: Explicit deadline within 24 hours, "ASAP", "urgent", "immediately"
  - high: VIP sender, deadline within 1 week, financial/legal implications
  - normal: Standard requests with reasonable or no explicit timeframe
  - low: Nice-to-have, "when you get a chance", no deadline

outputs:
  - For detect_todos:
      todos_found: list[TodoItem]
      duplicates_skipped: int
      source_email_ids: list[str]

  - For list_todos:
      todos: list[TodoItem]
      grouped_by_status:
        due_today: list[TodoItem]
        due_this_week: list[TodoItem]
        overdue: list[TodoItem]
        no_deadline: list[TodoItem]

  - TodoItem:
      id: str
      title: str                    # Brief description of the task
      description: str              # Full context
      category: str                 # self_reminder, request_received, etc.
      priority: str                 # urgent, high, normal, low
      status: str                   # pending, completed, snoozed
      due_date: date | null
      source_type: str              # email, meeting, manual
      source_id: str                # email_id or meeting_id
      source_summary: str           # "Request from Laura Hodgson, Jan 18"
      contact_name: str | null      # Who made the request (if applicable)
      contact_email: str | null
      created_at: datetime
      completed_at: datetime | null
      snoozed_until: date | null

human_approval_required:
  - None (todos are tracked internally, no external actions)
```

### Clarifier Agent

```yaml
agent:
  name: clarifier
  type: task
  layer: sub-agent

description: |
  Identifies emails where the next steps are ambiguous and drafts a
  clarifying email for Dave's review. Ensures Dave never acts on
  incomplete or unclear information.

capabilities:
  - detect_ambiguity      # Analyze email for unclear elements
  - generate_questions    # Create specific clarifying questions
  - draft_clarification   # Draft email requesting clarification
  - list_ambiguous        # Get all emails flagged as needing clarification

requires_context:
  - Email content and thread history
  - Sender's contact profile
  - Dave's voice profile (for drafting)
  - Previous clarification requests (avoid asking same thing twice)
  - Related emails (for additional context)

ambiguity_triggers:
  - missing_deadline: "soon", "later", "next week" without specific date
  - unclear_ownership: "someone", "the team", passive voice assignments
  - vague_request: "help with", "thoughts on" without specifics
  - multiple_interpretations: Could mean different things
  - incomplete_information: Missing who/what/when/where/why
  - contradictory_elements: Conflicting information in same email

classification_rules:
  - high_ambiguity: 3+ triggers, or actionable email with no clear next step
  - medium_ambiguity: 1-2 triggers, some clarity needed
  - low_ambiguity: Minor clarification helpful but not blocking
  - clear: No clarification needed

draft_guidelines:
  - tone: Professional, warm, direct (matching Dave's voice)
  - structure: Acknowledge what's clear, then ask specific questions
  - questions: 2-4 specific questions (not open-ended)
  - length: 3-5 sentences max
  - never_say: "I'm confused", "I don't understand" (frame positively)

outputs:
  - For detect_ambiguity:
      is_ambiguous: bool
      ambiguity_level: str          # high, medium, low, clear
      triggers_found: list[str]     # Which ambiguity triggers detected
      suggested_questions: list[str]
      confidence: float

  - For draft_clarification:
      draft_subject: str            # Usually "Re: [original subject]"
      draft_body: str
      to: list[str]
      cc: list[str]
      questions_asked: list[str]    # The specific questions in the draft
      context_preserved: str        # What was acknowledged as clear
      confidence: float
      notes_for_dave: str           # Any additional context

  - For list_ambiguous:
      ambiguous_emails: list[AmbiguousEmail]
      high_priority_count: int
      drafts_ready_count: int

  - AmbiguousEmail:
      email_id: str
      subject: str
      sender: str
      received_at: datetime
      ambiguity_level: str
      triggers: list[str]
      draft_ready: bool
      draft_id: str | null

human_approval_required:
  - draft_clarification (before sending any clarifying email)
```

### Meeting Agent

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

### Calendar Agent

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

### Briefing Agent

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

### Draft Agent

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

### Property Agent

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

### Research Agent

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

---

## Sub-Agent Base Interface

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

*Continue to [03-orchestrator.md](03-orchestrator.md) for Sage Orchestrator details.*
