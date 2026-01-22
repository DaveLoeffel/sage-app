# Sage Agent Architecture: Overview

**Version:** 1.5
**Created:** January 2026
**Last Updated:** January 22, 2026
**Status:** Context-Aware Chat Functional (Phase 3.9 Complete)

---

## Document Index

This architecture documentation is split into focused files for easier maintenance:

| Document | Description |
|----------|-------------|
| [00-overview.md](00-overview.md) | Executive summary, design principles, information flow (this file) |
| [01-data-layer.md](01-data-layer.md) | Layer 1: Data Layer, Indexer Agent, schemas, DataLayerService |
| [02-sub-agents.md](02-sub-agents.md) | Layer 2: Search Agent and all 10 task agent specifications |
| [03-orchestrator.md](03-orchestrator.md) | Layer 3: Sage Orchestrator, intent recognition, routing |
| [04-data-flow.md](04-data-flow.md) | Agent communication protocol and data flow examples |
| [05-implementation.md](05-implementation.md) | Implementation guide, directory structure, migration path |

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
│  │  Email   │ │ Follow-Up│ │ TodoList │ │ Clarifier│ │ Meeting  │  │
│  │  Agent   │ │  Agent   │ │  Agent   │ │  Agent   │ │  Agent   │  │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘ └──────────┘  │
│                                                                      │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐  │
│  │ Calendar │ │ Briefing │ │  Draft   │ │ Property │ │ Research │  │
│  │  Agent   │ │  Agent   │ │  Agent   │ │  Agent   │ │  Agent   │  │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘ └──────────┘  │
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

## Quick Reference: Agent Summary

| Agent | Layer | Purpose | Status |
|-------|-------|---------|--------|
| **Indexer** | Data | Ingests and indexes all data | COMPLETE |
| **Search** | Sub-Agent | Retrieves context for all agents | COMPLETE |
| **Email** | Task | Analyzes emails, drafts replies | PARTIAL |
| **Follow-Up** | Task | Tracks commitments, reminders | COMPLETE |
| **TodoList** | Task | Tracks action items from emails/meetings | COMPLETE |
| **Clarifier** | Task | Identifies ambiguous emails | PLANNED |
| **Meeting** | Task | Meeting prep and action extraction | PARTIAL |
| **Calendar** | Task | Schedule queries, conflict detection | PARTIAL |
| **Briefing** | Task | Daily/weekly briefings | PARTIAL |
| **Draft** | Task | Writes in Dave's voice | PARTIAL |
| **Property** | Task | Property metrics and analysis | PLANNED |
| **Research** | Task | External information gathering | PLANNED |

---

*Continue to [01-data-layer.md](01-data-layer.md) for Data Layer details.*
