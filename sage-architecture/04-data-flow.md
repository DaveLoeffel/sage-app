# Sage Agent Architecture: Data Flow & Communication

**Part of:** [Sage Architecture Documentation](00-overview.md)

---

## Agent Communication Protocol

### Message Format

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

### Communication Patterns

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

### Error Handling

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

## Data Flow Examples

### Example 1: New Email Arrives

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

### Example 2: User Asks "What's overdue?"

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

### Example 3: TodoList Scanning New Emails

```
┌─────────────────────────────────────────────────────────────────────┐
│ Trigger: New batch of emails synced (scheduled every 5 minutes)     │
└─────────────────────────────────┬───────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────┐
│ Orchestrator routes to: TodoList Agent                              │
│ Task: detect_todos for new emails                                   │
└─────────────────────────────────┬───────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────┐
│ TodoList Agent requests context from Search Agent:                  │
│                                                                     │
│ Search Agent gathers:                                               │
│ ┌─────────────────────────────────────────────────────────────────┐ │
│ │ • New emails not yet scanned for todos                          │ │
│ │ • VIP contacts list (for priority assignment)                   │ │
│ │ • Existing todo items (to check for duplicates)                 │ │
│ │ • Calendar events (for deadline context)                        │ │
│ └─────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────┬───────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────┐
│ TodoList Agent analyzes each email:                                 │
│                                                                     │
│ Email 1: From Laura Hodgson                                         │
│ - Contains: "Can you send me the Q4 numbers by Friday?"             │
│ - Detected: request_received                                        │
│ - Priority: high (VIP sender + deadline)                            │
│ - Due date: Friday (extracted from content)                         │
│                                                                     │
│ Email 2: Self-email (Dave to Dave)                                  │
│ - Subject: "Reminder: call insurance agent"                         │
│ - Detected: self_reminder                                           │
│ - Priority: normal                                                  │
│ - Due date: none specified                                          │
│                                                                     │
│ Email 3: From vendor                                                │
│ - Contains: general information, no requests                        │
│ - Detected: no todo                                                 │
└─────────────────────────────────┬───────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────┐
│ TodoList Agent creates todo items:                                  │
│ 1. "Send Q4 numbers to Laura" - due Friday, high priority           │
│ 2. "Call insurance agent" - no deadline, normal priority            │
│                                                                     │
│ Sends to Indexer Agent for storage                                  │
└─────────────────────────────────┬───────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────┐
│ Result: 2 todos created, 1 email skipped (no action items)          │
│ Available for: Daily briefing, Dashboard, Todo list queries         │
└─────────────────────────────────────────────────────────────────────┘
```

### Example 4: Clarifier Agent Detecting Ambiguity

```
┌─────────────────────────────────────────────────────────────────────┐
│ Trigger: Incoming email flagged as "action_required" by Email Agent │
└─────────────────────────────────┬───────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────┐
│ Orchestrator routes to: Clarifier Agent                             │
│ Task: detect_ambiguity                                              │
└─────────────────────────────────┬───────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────┐
│ Clarifier Agent requests context:                                   │
│                                                                     │
│ Search Agent gathers:                                               │
│ ┌─────────────────────────────────────────────────────────────────┐ │
│ │ • Full email content                                            │ │
│ │ • Thread history (previous messages)                            │ │
│ │ • Sender's contact profile                                      │ │
│ │ • Previous clarification requests to this sender                │ │
│ └─────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────┬───────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────┐
│ Clarifier Agent analyzes email:                                     │
│                                                                     │
│ Email content:                                                      │
│ "Hey Dave, we should sync up about the project soon.                │
│  Let me know your thoughts."                                        │
│                                                                     │
│ Ambiguity triggers detected:                                        │
│ ✓ missing_deadline: "soon" (no specific date)                       │
│ ✓ vague_request: "sync up about the project" (which project?)       │
│ ✓ unclear_scope: "thoughts" (on what specifically?)                 │
│                                                                     │
│ Result: high_ambiguity (3 triggers)                                 │
└─────────────────────────────────┬───────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────┐
│ Clarifier Agent generates clarifying questions:                     │
│                                                                     │
│ 1. When would you like to meet? (next day, week?)                   │
│ 2. Which project - Park Place renovations or Chateau DSCR?          │
│ 3. Should I prepare specific materials for our discussion?          │
└─────────────────────────────────┬───────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────┐
│ Clarifier Agent drafts email (using Draft Agent):                   │
│                                                                     │
│ Subject: Re: Project sync                                           │
│                                                                     │
│ Hi [Name],                                                          │
│                                                                     │
│ Happy to sync up. A few quick questions so I can prepare:           │
│                                                                     │
│ 1. What day/time works best for you?                                │
│ 2. Are you referring to the Park Place renovations or the           │
│    Chateau DSCR discussions?                                        │
│ 3. Anything specific you'd like me to bring to the table?           │
│                                                                     │
│ [signature]                                                         │
│                                                                     │
│ Status: DRAFT (requires Dave's approval to send)                    │
└─────────────────────────────────┬───────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────┐
│ Result: Email flagged as ambiguous                                  │
│ Draft ready for Dave's review in morning briefing                   │
│ Action: Dave reviews draft → approves/edits → sends                 │
└─────────────────────────────────────────────────────────────────────┘
```

### Example 5: Morning Briefing Generation

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

*Continue to [05-implementation.md](05-implementation.md) for implementation guide and migration path.*
