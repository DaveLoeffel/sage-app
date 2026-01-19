# SAGE: AI Executive Assistant
## Complete System Specification for Dave Loeffel

**Document Version:** 2.1
**Created:** January 2025
**Last Updated:** January 2026
**System Name:** Sage
**Owner:** Dave Loeffel, CFA | Highlands Residential, LLC
**Implementation Status:** Architecture Finalized, Implementation In Progress

**Related Documents:**
- [Agent Architecture](sage-agent-architecture.md) — Detailed three-layer system design

---

## Executive Summary

Sage is a personalized AI executive assistant that provides Dave Loeffel with 100% context persistence, intelligent follow-up tracking, and unified data synthesis across all professional and personal domains. The system eliminates dropped follow-ups, reduces cognitive load, and provides proactive intelligence through daily briefings and weekly reviews.

### Three-Layer Architecture

Sage is built on a three-layer multi-agent architecture:

| Layer | Purpose | Key Components |
|-------|---------|----------------|
| **Data Layer** | Store and index all information | PostgreSQL, Qdrant, Redis + Indexer Agent |
| **Sub-Agent Layer** | Specialized task execution | Email, Follow-Up, Meeting, Calendar, Briefing, Draft, Property, Research Agents + Search Agent |
| **Orchestrator Layer** | User interaction and coordination | Sage Orchestrator |

See [sage-agent-architecture.md](sage-agent-architecture.md) for complete architecture details.

**Primary Success Metric (30-Day):** Bulletproof follow-up tracking—no email falls through the cracks.

**Core Principles:**
1. **100% Access** – Unified knowledge across email, meetings, documents, and personal life
2. **100% Persistence** – Nothing forgotten; every conversation indexed for future recall
3. **100% Accuracy** – Multi-source verification; conflicts surfaced for human decision
4. **Human-in-the-Loop** – Draft only, never send; recommend but never authorize spending

---

## Table of Contents

1. [User Profile & Context](#1-user-profile--context)
2. [System Architecture](#2-system-architecture) — *See also: [sage-agent-architecture.md](sage-agent-architecture.md)*
3. [Technology Stack](#3-technology-stack)
4. [Data Layer & Indexing](#4-data-layer--indexing)
5. [Sub-Agent Specifications](#5-sub-agent-specifications)
6. [Integration Details](#6-integration-details)
7. [Autonomy & Safety Protocols](#7-autonomy--safety-protocols)
8. [Implementation Roadmap](#8-implementation-roadmap)
9. [Setup Checklist](#9-setup-checklist)
10. [Testing Criteria](#10-testing-criteria)
11. [Appendices](#11-appendices)

---

## 1. User Profile & Context

### 1.1 Professional Identity

| Field | Value |
|-------|-------|
| Name | Dave Loeffel, CFA |
| Role | CEO, Highlands Residential, LLC |
| Email | DLoeffel@HighlandsResidential.com |
| Cell | 404.432.8353 |
| Website | daveloeffel.com |
| LinkedIn Social | https://www.linkedin.com/in/daveloeffel/ |
| X-Twitter Social | https://x.com/DaveLoeffel |
| Facebook Social | https://www.facebook.com/daveloeffel |

### 1.2 Email Signature (Universal)
```
Dave Loeffel, CFA
Highlands Residential, LLC
cell: 404.432.8353
DLoeffel@HighlandsResidential.com
www.HighlandsResidential.com
```

### 1.3 Communication Style
- **Tone:** Formal but not stuffy; consistent across all recipients
- **Voice Source:** Learn from sent folder (do not use templates)
- **No consistent sign-offs or catchphrases**

### 1.4 Properties Managed

#### Park Place by Highlands
| Field | Value |
|-------|-------|
| Address | 77 East Pike St, Lawrenceville, GA 30046 |
| Website | https://parkplace.byhighlands.com/ |
| Units | 148 total |
| Occupancy | 130 occupied, 131 leased |
| Type | 3 buildings, 4-5 story splits, elevators, surface parking |
| Demographics | Active Adult 55+; primarily widows 65-80 |
| Positioning | Cost is 25% above market apartments and also 40% below independent living |
| Amenities | Clubroom, game room, library, secondary clubroom with view, shuffleboard, pavilion/grill, bocce ball, putting green, fire pit |
| Current Focus | Complete lease-up by end of Feb 2026; pivot to operational excellence |
| Critical Deadline | Loan matures May 2026 (extend, refinance, or sell) |

#### The Chateau by Highlands
| Field | Value |
|-------|-------|
| Address | 1670 Friendship Road, Hoschton, GA 30548 |
| Website | https://thechateau.byhighlands.com/ |
| Units | 152 total |
| Occupancy | 145 occupied, 146 leased |
| Type | 1 building, 3-story, 3 elevators, surface parking, open detention |
| Demographics | Active Adult 55+; primarily widows 65-80 |
| Positioning | Same as Park Place |
| Amenities | Clubroom, game room, library, secondary clubroom, swimming pool, pavilion/grill, bocce ball, putting green, fire pit |
| Current Focus | Transition from lease-up spending to operational excellence |
| Critical Deadline | DSCR test Nov 2026 (need 1.20x coverage = higher rents, lower expenses) |

### 1.5 Key Contacts

#### Highlands Residential Team
| Name | Role | Email | Reports To | Response Time |
|------|------|-------|------------|---------------|
| Laura Hodgson | Business Financials & Investor Relations | lhodgson@highlandsresidential.com | Dave | 1 business days |
| Welton McCrary | Senior Operations | - | Dave | 2 business days |
| Marci McGovney | Property Manager Supervisor | - | Welton | 2 business days |
| Yanet Rodriguez | Property Manager, The Chateau | - | Marci | 2 business days |
| Kelley Colgrove | Property Manager, Park Place | - | Marci | 2 business days |

#### External Partners
| Name | Role | Contact |
|------|------|---------|
| J. Mike Williams, Esq. | Legal Counsel | mwilliams@apartmentlaw.com, (404) 633-5114, Fowler, Hein, Cheatwood & Williams P.A. |
| Brad Brezina, CIC | Insurance | bbrezina@sspins.com, C: (678) 264-7287, Sterling Seacrest Pritchard |
| Steve Hinkle | Banker | steve.hinkle@wellsfargo.com,  C: (404) 822-6279, Wells Fargo|

#### Investor Communications
- 3 main business partners in Highlands (Tim Schrager, Aaron Goldman, Robert LaChapelle)
- Dozens of property investors
- Quarterly update cadence
- Standard format exists (examples to be provided)
- Expected response time: 3 business days

### 1.6 Family

| Name | Relationship | DOB | Notes |
|------|--------------|-----|-------|
| Laura Loeffel | Wife | 05/14/1977 | Anniversary: 09/27/2003; handles school/family logistics; uses Pocket Informant for calendar |
| Nate Loeffel | Son | 10/18/2007 | Software engineer; may play tennis spring 2026; drives himself; can advise on technical issues (no data access) |
| Luke Loeffel | Son | 02/13/2010 | May play golf spring 2026; turns 16 Feb 2026 (will drive); currently 2026 Toyota Tacoma SR |
| Sophia Loeffel | Daughter | 11/23/2012 | Track (sprinter) for Fellowship Christian School + Pope Greyhounds Track Club |

#### Residences
| Property | Address |
|----------|---------|
| Main Home | 1513 Murdock Road, Marietta, GA 30062 |
| Lake House | 2198 Thunder Oak Road, Young Harris, GA 30582 |

#### Vehicles
| Owner | Vehicle |
|-------|---------|
| Dave | 2018 Lexus 350 RXL |
| Laura | 2020 Ford Expedition |
| Nate | 2023 Toyota Rav4 |
| Luke | 2026 Toyota Tacoma SR |

### 1.7 Email Distribution (by category)
- Immediate action required: 5%
- Informational/FYI: 10%
- Ongoing threads: 20%
- Tenant-related: 1%
- Property-related: 24%
- Personal: 10%
- Junk: ~30%

---

## 2. System Architecture

> **Detailed Architecture:** See [sage-agent-architecture.md](sage-agent-architecture.md) for complete system design, agent specifications, and implementation details.

### 2.1 Three-Layer Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                         USER INTERFACE                               │
│                    (Chat, Dashboard, API)                            │
└─────────────────────────────────┬───────────────────────────────────┘
                                  │
┌─────────────────────────────────▼───────────────────────────────────┐
│              LAYER 3: SAGE ORCHESTRATOR                              │
│   Routes requests • Coordinates agents • Maintains conversation      │
└─────────────────────────────────┬───────────────────────────────────┘
                                  │
┌─────────────────────────────────▼───────────────────────────────────┐
│                    LAYER 2: SUB-AGENTS                               │
│  ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐  │
│  │ Email  │ │Follow- │ │Meeting │ │Calendar│ │Briefing│ │ Draft  │  │
│  │ Agent  │ │Up Agent│ │ Agent  │ │ Agent  │ │ Agent  │ │ Agent  │  │
│  └────────┘ └────────┘ └────────┘ └────────┘ └────────┘ └────────┘  │
│                    ┌──────────────────────┐                         │
│                    │    SEARCH AGENT      │                         │
│                    │ (context retrieval)  │                         │
│                    └──────────────────────┘                         │
└─────────────────────────────────┬───────────────────────────────────┘
                                  │
┌─────────────────────────────────▼───────────────────────────────────┐
│                      LAYER 1: DATA LAYER                             │
│                    ┌──────────────────────┐                         │
│                    │    INDEXER AGENT     │                         │
│                    │ (ingests & indexes)  │                         │
│                    └──────────────────────┘                         │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────────────────┐ │
│  │PostgreSQL│  │  Qdrant  │  │  Redis   │  │   External APIs      │ │
│  │(relational)│ │(vectors) │  │ (cache)  │  │ Gmail/Calendar/etc.  │ │
│  └──────────┘  └──────────┘  └──────────┘  └──────────────────────┘ │
└─────────────────────────────────────────────────────────────────────┘
```

### 2.2 Key Architectural Concepts

| Concept | Description |
|---------|-------------|
| **Indexer Agent** | Ingests all data (emails, meetings, conversations) and stores in search-optimized format |
| **Search Agent** | Retrieves relevant context for any sub-agent task; single point of data access |
| **Conversation Memory** | Every exchange with Sage is indexed; facts, decisions, and preferences are extracted and remembered |
| **Sub-Agent Specialization** | Each agent has focused capabilities (e.g., Follow-Up Agent only handles follow-ups) |
| **Orchestrator** | Routes user requests to appropriate agents, coordinates multi-agent workflows |

### 2.3 Data Flow

```
┌──────────────────────────────────────────────────────────────────┐
│                        DAILY CYCLE                               │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│   6:00 AM ─► Overnight email scan                               │
│          ─► Calendar context enrichment                          │
│          ─► Property report ingestion (if received)              │
│          ─► News/stock updates                                   │
│          ─► Follow-up deadline check                             │
│                    │                                             │
│                    ▼                                             │
│   6:30 AM ─► MORNING BRIEFING generated                         │
│          ─► Sent to Dave's inbox                                 │
│                    │                                             │
│                    ▼                                             │
│   Ongoing ─► Follow-up monitoring                                │
│          ─► Draft emails on request                              │
│          ─► Meeting prep on demand                               │
│          ─► MindDatabase updates                                 │
│                    │                                             │
│                    ▼                                             │
│   Evening ─► Daily digest of confidence-flagged actions          │
│          ─► Productivity enhancement suggestions                 │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────┐
│                       WEEKLY CYCLE                               │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│   Saturday AM ─► Weekly review generation                        │
│              ─► What worked well                                 │
│              ─► What fell through cracks                         │
│              ─► Upcoming deadlines                               │
│              ─► Suggested priorities                             │
│              ─► Knowledge review (confirm/update MindDatabase)   │
│              ─► SOP recommendations                              │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

### 2.3 Directory Structure

```
~/Projects/claude-sage/
├── sage-specification.md          # This document
├── ideas.md                       # Brainstorming and planning notes
└── sage/                          # Main application directory
    ├── README.md                  # Quick start guide
    ├── Makefile                   # Development commands
    ├── docker-compose.yml         # Container orchestration
    ├── .env.example               # Environment template
    │
    ├── backend/                   # Python FastAPI backend
    │   ├── pyproject.toml         # Python dependencies
    │   ├── Dockerfile
    │   ├── alembic/               # Database migrations
    │   │   ├── versions/
    │   │   │   ├── 001_initial_schema.py
    │   │   │   └── 002_extend_picture_column.py
    │   │   └── env.py
    │   │
    │   └── sage/
    │       ├── main.py            # FastAPI entry point
    │       ├── config.py          # Settings management
    │       ├── api/               # REST endpoints
    │       │   ├── auth.py
    │       │   ├── emails.py
    │       │   ├── followups.py
    │       │   ├── calendar.py
    │       │   ├── briefings.py
    │       │   ├── chat.py
    │       │   ├── dashboard.py
    │       │   └── meetings.py
    │       ├── core/              # Business logic
    │       │   ├── claude_agent.py
    │       │   ├── followup_tracker.py
    │       │   └── briefing_generator.py
    │       ├── models/            # SQLAlchemy ORM models
    │       │   ├── user.py
    │       │   ├── email.py
    │       │   ├── contact.py
    │       │   └── followup.py
    │       ├── schemas/           # Pydantic validation schemas
    │       ├── services/          # Database, vector search
    │       ├── mcp/               # MCP servers (Fireflies, etc.)
    │       └── scheduler/         # APScheduler background jobs
    │
    │   └── tests/                 # Pytest test suite
    │
    ├── frontend/                  # Next.js frontend
    │   ├── package.json
    │   ├── Dockerfile
    │   └── src/
    │       ├── app/               # Pages
    │       ├── components/        # React components
    │       └── lib/               # Utilities
    │
    └── scripts/                   # Setup and utility scripts
```

---

## 3. Technology Stack

### 3.1 Core Technologies

| Layer | Technology | Version | Purpose |
|-------|------------|---------|---------|
| **Backend Framework** | FastAPI | 0.115+ | Async REST API |
| **Language** | Python | 3.12+ | Backend logic |
| **Database** | PostgreSQL | 16 | Persistent storage |
| **ORM** | SQLAlchemy | 2.0+ | Async database operations |
| **Migrations** | Alembic | Latest | Schema versioning |
| **Vector DB** | Qdrant | Latest | Semantic search |
| **Cache** | Redis | 7 | Session/query caching |
| **Task Scheduler** | APScheduler | Latest | Background jobs |
| **AI** | Anthropic Claude | claude-sonnet-4-20250514 | Analysis and generation |
| **Frontend** | Next.js | 15 | React web application |
| **UI Library** | React | 19 | Component framework |
| **Styling** | TailwindCSS | 3.4 | CSS utilities |
| **Auth** | NextAuth | 5.0 | OAuth handling |
| **Containerization** | Docker Compose | Latest | Service orchestration |

### 3.2 Python Dependencies

```toml
# pyproject.toml (key dependencies)
[tool.poetry.dependencies]
python = "^3.12"
fastapi = "^0.115.0"
uvicorn = "^0.32.0"
sqlalchemy = "^2.0"
asyncpg = "^0.30.0"
alembic = "^1.14.0"
pydantic = "^2.10.0"
pydantic-settings = "^2.6.0"
anthropic = "^0.40.0"
google-api-python-client = "^2.153.0"
google-auth-oauthlib = "^1.2.1"
httpx = "^0.28.0"
python-jose = "^3.3.0"
passlib = "^1.7.4"
apscheduler = "^3.10.4"
qdrant-client = "^1.12.1"
sentence-transformers = "^3.3.1"
redis = "^5.2.0"
python-multipart = "^0.0.18"
fastmcp = "^0.1.0"
```

### 3.3 Required Accounts & APIs

| Service | Purpose | Setup Required | Status |
|---------|---------|----------------|--------|
| Anthropic | Claude API | API key from console.anthropic.com | **Required** |
| Google Cloud | Gmail, Calendar, Drive APIs | OAuth credentials | **Required** |
| Fireflies.ai | Meeting transcripts | API key (Business plan) | **Implemented** |
| Alpha Vantage | Stock prices | Free API key | Optional |
| Cloudflare | Remote tunnel access | Tunnel token | Optional (prod) |

### 3.4 Frontend Dependencies

```json
// package.json (key dependencies)
{
  "dependencies": {
    "next": "15.0.3",
    "react": "19.0.0-rc",
    "react-dom": "19.0.0-rc",
    "@radix-ui/react-*": "^1.x",
    "@tanstack/react-query": "^5.60.5",
    "axios": "^1.7.8",
    "lucide-react": "^0.460.0",
    "recharts": "^2.14.1",
    "tailwindcss": "^3.4.15",
    "next-auth": "5.0.0-beta.25",
    "typescript": "^5.6.3"
  }
}
```

---

## 4. Data Layer & Indexing

> **Detailed Schemas:** See [sage-agent-architecture.md](sage-agent-architecture.md) Section 2 for complete index schemas, memory structures, and data flow.

### 4.1 Design Principles

1. **Search-Optimized:** All data indexed for fast semantic and structured retrieval
2. **Memory-Persistent:** Every conversation captured; facts, decisions, and preferences extracted
3. **Relationship-Aware:** Entities linked together (email ↔ contact ↔ follow-up ↔ meeting)
4. **Supersession-Tracked:** New facts override old ones while maintaining audit trail

### 4.2 Entity Types

| Entity Type | Description | Key Fields |
|-------------|-------------|------------|
| **Email** | Cached Gmail messages | subject, sender, category, priority, action_items |
| **Contact** | People Dave interacts with | name, email, role, organization, supervisor |
| **Follow-up** | Tracked commitments | subject, due_date, status, escalation_contact |
| **Meeting** | Calendar events + transcripts | attendees, notes, action_items |
| **Memory** | Conversation turns | user_message, sage_response, facts_extracted |
| **Property** | Park Place & Chateau | occupancy, metrics, issues, deadlines |

### 4.3 Memory Types

The Indexer Agent extracts and categorizes information from every conversation:

| Type | Description | Example |
|------|-------------|---------|
| `fact` | New information | "Luke's birthday is February 13" |
| `fact_correction` | Updates existing knowledge | "Deadline changed from Jan 31 to Feb 15" |
| `decision` | Choice made by Dave | "Use Sterling Seacrest for insurance" |
| `preference` | User preference | "Don't schedule meetings before 9am" |
| `task` | Something to remember | "Review Q4 update by Monday" |

---

## 5. Sub-Agent Specifications

> **Detailed Agent Specs:** See [sage-agent-architecture.md](sage-agent-architecture.md) Section 3 for complete agent specifications, capabilities, and implementation details.

### 5.1 Agent Overview

| Agent | Purpose | Status |
|-------|---------|--------|
| **DataLayerService** | Bridges agents to storage (PostgreSQL, Qdrant) | **COMPLETE** |
| **Indexer Agent** | Ingests data, generates embeddings, maintains indexes | PLANNED |
| **Search Agent** | Retrieves context for all other agents | PLANNED |
| **Email Agent** | Analyzes emails, drafts replies | PARTIAL |
| **Follow-Up Agent** | Tracks commitments, generates reminders | COMPLETE |
| **Meeting Agent** | Prepares meeting context, extracts actions | PARTIAL |
| **Calendar Agent** | Manages schedule queries, detects conflicts | PARTIAL |
| **Briefing Agent** | Generates morning and weekly briefings | PARTIAL |
| **Draft Agent** | Writes content in Dave's voice | PARTIAL |
| **Property Agent** | Property metrics and analysis | PLANNED |
| **Research Agent** | External information gathering | PLANNED |

### 5.2 Follow-Up Agent — **COMPLETE**
*Primary success metric: No email falls through the cracks*

#### Escalation Timeline

| Day | Action |
|-----|--------|
| 0 | Email sent, follow-up created |
| 2 | Gentle reminder drafted (human approval required) |
| 7 | Escalation drafted with supervisor CC |
| 7+ | Dashboard alert for Dave to prioritize |

### 5.3 Briefing Agent — **PARTIAL**
*Generation works, email delivery pending*

**Morning Briefing** (6:30 AM ET):
- Urgent attention items
- Today's calendar with context
- Overdue and due-today follow-ups
- Property metrics snapshot
- AI-generated priorities

**Weekly Review** (Saturday 8 AM ET):
- Week's accomplishments
- Items that fell through
- Upcoming deadlines
- Suggested priorities
- Knowledge review questions

### 5.4 Meeting Agent — **PARTIAL**

Generates meeting prep including:
- Attendee context and relationships
- Recent emails with attendees
- Previous meeting notes (Fireflies)
- Open follow-ups with attendees
- Suggested discussion points

### 5.5 Calendar Agent — **PARTIAL**

**Data Sources:**
- Dave's Google Calendar
- Laura's calendar (Pocket Informant export)
- Kids' sports (TeamSnap, SportsEngine)

**Capabilities:**
- Unified schedule view
- Conflict detection
- Family event coordination

### 5.6 Other Agents

| Agent | Status | Key Capability |
|-------|--------|----------------|
| **Email Agent** | PARTIAL | Categorization, draft replies |
| **Draft Agent** | PARTIAL | Write in Dave's voice |
| **Property Agent** | PLANNED | Occupancy, metrics, competitor analysis |
| **Research Agent** | PLANNED | Web search, document retrieval |

### 5.7 Sample Outputs

**Morning Briefing Example:**
```
🚨 REQUIRES ATTENTION (3)
1. Email from Steve Hinkle - ROW dedication update
2. Follow-up overdue: Yanet/Renderings - Day 3
3. Sophia track meet today - conflicts with 3:30 call

📅 TODAY'S CALENDAR
9:00 AM  Weekly sync - Laura Hodgson
11:00 AM Vendor call - HVAC (Chateau unit 204)
3:30 PM  Call with Brad Brezina ⚠️ Conflict

✅ FOLLOW-UP STATUS
Pending: 8 | Overdue: 2 | Resolved yesterday: 3

💡 TODAY'S PRODUCTIVITY SUGGESTION
Consider creating an SOP for "Entrata Asset Update Requests" - this is the third time renderings have needed follow-up. A checklist could prevent delays.
```

---

## 6. Integration Details

### 6.1 Gmail (IMAP/SMTP)

#### Setup
1. Enable 2FA on Gmail account
2. Generate App Password: Google Account → Security → App Passwords
3. Store in .env file

#### Configuration
```yaml
# config/settings.yaml
email:
  imap_server: imap.gmail.com
  imap_port: 993
  smtp_server: smtp.gmail.com
  smtp_port: 587
  address: DLoeffel@HighlandsResidential.com
  use_ssl: true
```

#### Capabilities
- Read all emails (49,000+ accessible)
- Search by sender, subject, date, content
- Send emails (with explicit approval only)
- Track sent emails for follow-up

### 6.2 Google Calendar

#### Setup
1. Create Google Cloud Project
2. Enable Calendar API
3. Create OAuth 2.0 credentials
4. Download credentials.json
5. Run OAuth flow to generate token.json

#### Capabilities
- Read all calendars
- Create events (with approval)
- Modify events (with approval)
- Parse attendee information

### 6.3 Google Drive

#### Setup
Same Google Cloud Project as Calendar

#### Capabilities
- Search files by name, content
- Read document contents
- Access Fireflies folder: https://drive.google.com/drive/folders/12SD9KYhVoMTzZWWAwrjayDz7-LlYeRoF
- Store MindDatabase in synced folder

### 6.4 Fireflies.ai

#### Setup
1. Retrieve API key from Fireflies dashboard
2. Store in .env

#### Capabilities
- Fetch transcripts by date
- Search transcripts by participant, keyword
- Extract action items (Fireflies AI feature)

### 6.5 Plaud.ai

#### Integration Method
- Transcripts arrive via Zapier to Gmail
- Parse incoming emails from Plaud
- Extract transcript content
- Optional: Set up cloud folder sync

### 6.6 Entrata (Workaround)

#### Since API unavailable:
1. Configure automated reports in Entrata
2. Set reports to email daily to Dave
3. Sage parses incoming Entrata report emails
4. Extracts metrics: occupancy, delinquency, work orders, traffic, applications

### 6.7 QuickBooks Online

#### Purpose (Family Bookkeeping)
- Categorize transactions
- Remind to reconcile accounts
- Flag unusual expenses and subscriptions
- Prepare for tax time

#### Integration
- QBO has API; will require OAuth setup
- Or: Parse emailed reports/alerts

### 6.8 Notification Channels

#### Email
- All notifications sent to Gmail
- Part of morning briefing

#### SMS (Urgent Only)
- Requires Twilio account
- Used for: system offline alerts, truly urgent items

#### Dashboard (Phase 2)
- Web-based interface on Vercel
- Real-time follow-up status
- Task boards (Monday.com inspiration)

---

## 7. Autonomy & Safety Protocols

### 7.1 Core Principle

> **Draft only. Never send. Recommend but never authorize.**

### 7.2 Action Classification

| Action Type | Autonomy Level | Example |
|-------------|----------------|---------|
| Read | Autonomous | Reading emails, calendars, documents |
| Analyze | Autonomous | Summarizing, detecting follow-ups |
| Draft | Autonomous | Writing email drafts, reports |
| Create (internal) | Autonomous | Creating follow-up entries, MindDatabase updates |
| Send | Requires explicit approval | Sending any email |
| Schedule | Requires explicit approval | Adding calendar events |
| Modify (external) | Requires explicit approval | Editing shared docs |
| Spend | Never autonomous | Any financial authorization |

### 7.3 Double-Confirmation Protocol

For any action that leaves the system (sending, scheduling, modifying):

```
Step 1: Sage drafts action
Step 2: Sage presents draft to Dave with summary of what will happen
Step 3: Dave explicitly approves ("yes", "send it", "approved")
Step 4: Sage executes action
Step 5: Sage logs action in audit trail
```

### 7.4 Error Handling

| Error Type | Response |
|------------|----------|
| API failure | Retry 3x, then alert Dave via backup channel |
| Ambiguous request | Ask for clarification before proceeding |
| Conflicting information | Surface both sources, ask Dave to resolve |
| Confidence < 80% | Flag in daily digest, do not act |
| System offline > 1 hour | Send email alert "Sage offline, check email directly" |
| System offline > 4 hours | Send SMS alert |

### 7.5 Audit Trail

All actions logged to `logs/actions.log`:
```json
{
  "timestamp": "2025-01-15T10:30:00Z",
  "action_type": "email_draft",
  "description": "Drafted follow-up to Yanet re: renderings",
  "status": "pending_approval",
  "confidence": 0.95,
  "requires_approval": true,
  "approved": null,
  "executed": null
}
```

### 7.6 Daily Productivity Recommendations

Each evening, Sage analyzes the day and suggests:
- Process improvements
- SOP candidates (repeated tasks that could be standardized)
- Efficiency gains
- Tools or integrations that could help

### 7.7 Data Access Boundaries

| Person | Access Level |
|--------|--------------|
| Dave | Full access to all data |
| Nate | Code only; no access to email, contacts, family info |
| Laura (wife) | Can view family calendar; no business access |
| No one else | No access |

---

## 8. Implementation Roadmap

### Current Status (January 2026)

The Sage system has progressed significantly from the original specification. Core infrastructure is operational and ready for daily use testing.

### Implementation Summary

| Phase | Original Scope | Status | Notes |
|-------|---------------|--------|-------|
| Foundation | Dev environment | **COMPLETE** | Docker-based, Python 3.12 |
| MindDatabase | Knowledge store | **PIVOTED** | Using PostgreSQL + Claude context |
| Calendar | Unified view | **PARTIAL** | API integrated, needs UI polish |
| Meeting Prep | Auto context | **COMPLETE** | Fireflies MCP integrated |
| Follow-Up Tracker | Bulletproof tracking | **COMPLETE** | Full state machine implemented |
| Morning Briefing | Daily email | **COMPLETE** | Generation works, email delivery TODO |
| Voice Training | Email drafts | **PARTIAL** | System prompt captures style |
| Dashboard | Web interface | **IN PROGRESS** | Structure built, needs polish |
| Weekly Review | Saturday summary | **COMPLETE** | Generation works |

### Completed Components

#### Infrastructure (100%)
- [x] Docker Compose orchestration (PostgreSQL, Redis, Qdrant, Backend, Frontend)
- [x] FastAPI backend with async SQLAlchemy
- [x] Database schema with Alembic migrations
- [x] Google OAuth authentication
- [x] APScheduler for background jobs
- [x] Pytest test suite

#### Email Management (90%)
- [x] Gmail sync via Google API (every 5 minutes)
- [x] AI-powered categorization (urgent, action_required, fyi, newsletter, personal, spam)
- [x] Priority assignment (urgent, high, normal, low)
- [x] Vector indexing with Qdrant for semantic search
- [x] Email analysis (summary, action items, sentiment)
- [ ] TODO: Actual email sending (currently draft-only per human-in-the-loop)

#### Follow-Up Tracking (100%)
- [x] Auto-detection from sent emails
- [x] Full state machine: pending → reminded → escalated → completed/cancelled
- [x] Day 2 reminder draft generation
- [x] Day 7 escalation with supervisor CC
- [x] Auto-close when reply detected
- [x] Overdue grouping by severity
- [x] Complete REST API

#### Briefings (85%)
- [x] Morning briefing generation (daily 6:30 AM ET)
- [x] Weekly review generation (Saturdays 8 AM ET)
- [x] Integration with follow-ups, emails, calendar
- [x] AI-generated priorities and recommendations
- [ ] TODO: Email delivery (currently API-only)
- [ ] TODO: Stock prices integration
- [ ] TODO: Property metrics integration

#### Meeting Preparation (80%)
- [x] Attendee context from contacts database
- [x] Email history with participants
- [x] Fireflies transcript integration via MCP
- [x] Action item extraction
- [ ] TODO: Automatic delivery 30 min before meeting
- [ ] TODO: Post-meeting summary generation

#### Dashboard & UI (60%)
- [x] Next.js 15 / React 19 structure
- [x] Stats cards (overdue, pending, unread, completed)
- [x] Follow-up widget
- [x] Email widget
- [x] Calendar widget placeholder
- [ ] TODO: Polish and responsive design
- [ ] TODO: Quick actions implementation
- [ ] TODO: Charts and visualizations

#### AI Integration (90%)
- [x] Claude agent with comprehensive system prompt
- [x] Email analysis and categorization
- [x] Draft reply generation
- [x] Chat interface with conversation history
- [x] Thread summarization
- [ ] TODO: Voice profile training from sent folder

### Remaining Work

#### Phase A: Production Readiness
| Task | Priority | Effort |
|------|----------|--------|
| Email sending capability | High | Medium |
| Briefing email delivery | High | Low |
| Google Calendar full sync | Medium | Medium |
| Frontend polish & responsiveness | Medium | Medium |
| Meeting auto-delivery | Medium | Low |

#### Phase B: Enhanced Features
| Task | Priority | Effort |
|------|----------|--------|
| Stock price integration | Low | Low |
| Property metrics from Entrata | Medium | High |
| Voice profile from sent folder | Low | Medium |
| Family calendar overlay | Medium | Medium |
| Conflict detection alerts | Medium | Low |

#### Phase C: Operational Excellence
| Task | Priority | Effort |
|------|----------|--------|
| System monitoring & alerts | Medium | Medium |
| Performance optimization | Low | Medium |
| Mobile-responsive improvements | Low | Medium |
| Documentation completion | Low | Low |

### Quick Start (Current)

```bash
# Clone and navigate
cd ~/Projects/claude-sage/sage

# Copy environment file and configure
cp .env.example .env
# Edit .env with your API keys

# Start all services
make up

# Access
# Frontend: http://localhost:3000
# Backend API: http://localhost:8000
# API Docs: http://localhost:8000/docs

# Run tests
make test
```

---

## 9. Setup Checklist

### 9.1 Prerequisites

- [x] Docker Desktop installed
- [x] Git installed
- [x] Make installed (comes with Xcode Command Line Tools on macOS)
- [ ] Anthropic API key from console.anthropic.com
- [ ] Google Cloud Project with OAuth credentials
- [ ] Fireflies.ai API key (optional, for meeting transcripts)

### 9.2 Quick Setup

```bash
# 1. Navigate to project
cd ~/Projects/claude-sage/sage

# 2. Copy environment template
cp .env.example .env

# 3. Edit .env with your credentials
# Required:
#   SECRET_KEY=<generate with: openssl rand -hex 32>
#   ANTHROPIC_API_KEY=sk-ant-...
#   GOOGLE_CLIENT_ID=...
#   GOOGLE_CLIENT_SECRET=...

# 4. Start all services
make up

# 5. Run database migrations
make migrate

# 6. Access the application
# Frontend: http://localhost:3000
# Backend API: http://localhost:8000/docs
```

### 9.3 Google Cloud Setup

1. Go to https://console.cloud.google.com
2. Create new project: "Sage Assistant"
3. Enable APIs:
   - Gmail API
   - Google Calendar API
   - Google Drive API
4. Configure OAuth consent screen:
   - User Type: Internal (for Google Workspace) or External
   - App name: Sage
   - Scopes:
     - `https://www.googleapis.com/auth/gmail.readonly`
     - `https://www.googleapis.com/auth/gmail.send`
     - `https://www.googleapis.com/auth/calendar.readonly`
     - `https://www.googleapis.com/auth/drive.readonly`
5. Create OAuth 2.0 credentials:
   - Application type: Web application
   - Authorized redirect URIs: `http://localhost:8000/api/v1/auth/callback`
   - Copy Client ID and Client Secret to `.env`

### 9.4 Development Commands

```bash
# Service Management
make up           # Start all services (background)
make down         # Stop all services
make logs         # View logs (all services)
make dev          # Start with live output (foreground)

# Database
make migrate      # Run pending migrations
make migrate-new  # Create new migration

# Testing
make test         # Run all tests
make test-cov     # Run with coverage report

# Maintenance
make build        # Rebuild containers
make clean        # Remove all containers and volumes
```

### 9.5 Environment Variables Reference

```bash
# Core (Required)
SECRET_KEY=                     # JWT signing key
DATABASE_URL=                   # PostgreSQL async URL (auto-configured in Docker)
QDRANT_URL=                     # Vector DB URL (auto-configured in Docker)
REDIS_URL=                      # Cache URL (auto-configured in Docker)

# APIs (Required)
ANTHROPIC_API_KEY=              # Claude API key
GOOGLE_CLIENT_ID=               # Google OAuth client ID
GOOGLE_CLIENT_SECRET=           # Google OAuth client secret

# APIs (Optional)
FIREFLIES_API_KEY=              # Meeting transcripts
ALPHA_VANTAGE_API_KEY=          # Stock prices

# Frontend
NEXTAUTH_URL=http://localhost:3000
NEXTAUTH_SECRET=                # Generate with: openssl rand -hex 32
NEXT_PUBLIC_API_URL=http://localhost:8000
```

---

## 10. Testing Criteria

### 10.1 Infrastructure Tests
- [x] `make up` starts all services without errors
- [x] Health endpoint returns 200: `curl http://localhost:8000/health`
- [x] Database migrations complete successfully
- [x] Frontend loads at http://localhost:3000
- [x] API docs accessible at http://localhost:8000/docs

### 10.2 Authentication Tests
- [x] Google OAuth flow initiates correctly
- [x] User created on first login
- [x] JWT token generated and validated
- [ ] Token refresh works for long sessions

### 10.3 Email Tests
- [x] Gmail sync fetches emails via API
- [x] Emails categorized correctly (urgent, action_required, etc.)
- [x] Priority assigned appropriately
- [x] Vector indexing stores embeddings in Qdrant
- [x] Email analysis generates summary and action items
- [ ] Email sending works (pending implementation)

### 10.4 Follow-Up Tests (Primary Success Metric)
- [x] Sent email to key contact creates follow-up entry
- [x] Email with action phrases creates follow-up
- [x] Reply from recipient auto-closes follow-up
- [x] Day 2: reminder draft generated (state: reminded)
- [x] Day 7: escalation draft with supervisor CC (state: escalated)
- [x] REST API: GET /followups returns list
- [x] REST API: GET /followups/overdue returns overdue items
- [x] REST API: POST /followups/{id}/complete marks complete

### 10.5 Briefing Tests
- [x] Morning briefing generates via API
- [x] Contains email summary section
- [x] Contains follow-up status section
- [x] Contains AI-generated priorities
- [ ] Email delivery (pending implementation)
- [ ] Stock prices integration (pending)
- [ ] Calendar section populated (partial)

### 10.6 Meeting Prep Tests
- [x] Meeting list fetched from calendar
- [x] Attendee context retrieved from contacts
- [x] Fireflies integration returns transcripts
- [ ] Auto-delivery 30 min before meeting (pending)
- [ ] Open loops with attendees included (partial)

### 10.7 Chat Interface Tests
- [x] Chat endpoint accepts messages
- [x] Claude responds with context awareness
- [x] Conversation history maintained
- [x] Suggestions generated for follow-up questions

### 10.8 Dashboard Tests
- [x] Summary endpoint returns stats
- [x] Overdue count accurate
- [x] Pending count accurate
- [x] Unread emails count works
- [ ] Charts render correctly (pending frontend polish)

### 10.9 Full System Validation
- [ ] Can go one full week without dropped follow-up
- [ ] Morning briefing delivered and helpful 5/5 days
- [ ] Meeting prep used for 3+ meetings
- [ ] Weekly review generated Saturday morning
- [ ] Zero embarrassing emails sent (human-in-the-loop enforced)

### 10.10 Running Tests

```bash
# Run all backend tests
make test

# Run with coverage report
make test-cov

# Run specific test file
docker compose exec backend pytest tests/test_followups.py -v

# Run tests matching pattern
docker compose exec backend pytest -k "followup" -v
```

---

## 11. Appendices

### 11.1 Key URLs Reference

| Resource | URL |
|----------|-----|
| Dave's website | https://daveloeffel.com |
| Park Place | https://parkplace.byhighlands.com/ |
| The Chateau | https://thechateau.byhighlands.com/ |
| Fireflies Drive Folder | https://drive.google.com/drive/folders/12SD9KYhVoMTzZWWAwrjayDz7-LlYeRoF |
| Laura Hodgson Meeting Agenda | https://docs.google.com/document/d/1VC5N170Z1x9OT2BCWMkP-iyPeDab3JA1fEDIWRegfMI/ |
| FCS Calendar | https://www.fellowshipchristianschool.org/calendar-utility |
| FCS Tennis (Nate) | https://www.fellowshipchristianschool.org/.../158 |
| FCS Golf (Luke) | https://www.fellowshipchristianschool.org/.../162 |
| FCS Track (Sophia) | https://www.fellowshipchristianschool.org/.../161 |
| Pope Greyhounds (Sophia) | https://greyhoundtrackandcrosscountry.sportngin.com/ |

### 11.2 Contact Quick Reference

```yaml
# Quick copy for contact profiles

Highlands Residential:
  - Laura Hodgson: lhodgson@highlandsresidential.com (Financials/IR)
  - Marci McGovney: (Supervises PMs)
  - Kelley Colgrove: (PM - Park Place)
  - Yanet Rodriguez: (PM - The Chateau)
  - Welton McCrary: (Oversees Marci)

External:
  - J. Mike Williams: mwilliams@apartmentlaw.com (Legal)
  - Brad Brezina: (Insurance) C: 678-264-7287
  - Steve Hinkle: (Wells Fargo banker)

Family:
  - Laura Loeffel (wife): [calendar via Pocket Informant export]
  - Nate: 10/18/2007, tennis, drives himself
  - Luke: 02/13/2010, golf, turns 16 Feb 2026
  - Sophia: 11/23/2012, track (FCS + Pope Greyhounds)
```

### 11.3 Stock Ticker List

```
MSTR, TSLA, NVDA, PLTR, NUKZ, ALB, MP, POWL, TREE, ULTA, BTC
```

### 11.4 Competitor URLs (for pricing script)

**Park Place Active Adult:**
- annabelleonmain.com
- liveeverleigh.com/duluth
- liveeverleigh.com/alpharetta
- evoqjohnscreek.securecafe.com
- legacyatwaltonkennesawmountain.com
- outlookgwinnett.com
- liveoverture.com/overture-barrett
- liveoverture.com/overture-buckhead-south
- liveoverture.com/overture-powers-ferry

**Park Place Local:**
- livemargot.com (Lawrenceville)
- thewhitbywebbgin.com
- flatsatsouthlawn.com
- averlycollinshill.com

**The Chateau Local:**
- thefinchbraselton.com
- theharrisonatbraselton.com
- thelaurelapts.com
- claretvillagebraselton.com

### 11.5 Decision Log Template

```markdown
# Decision: [Title]

**Date:** YYYY-MM-DD
**Decision Maker:** Dave Loeffel
**Context:** [What situation required a decision]
**Options Considered:**
1. [Option A]
2. [Option B]
3. [Option C]

**Decision:** [What was chosen]
**Rationale:** [Why this option]
**Outcome:** [To be updated later]
```

### 11.6 SOP Template

```markdown
# SOP: [Process Name]

**Created:** YYYY-MM-DD
**Last Updated:** YYYY-MM-DD
**Owner:** [Who maintains this]

## Purpose
[Why this SOP exists]

## Trigger
[What initiates this process]

## Steps
1. [Step 1]
2. [Step 2]
3. [Step 3]

## Escalation
[When and how to escalate]

## Related Documents
- [Link 1]
- [Link 2]
```

---

## Document Control

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | January 2025 | Dave Loeffel + Claude | Initial specification |
| 2.0 | January 2026 | Dave Loeffel + Claude | Implementation progress documented; Technology stack updated (FastAPI, Docker); Directory structure populated; Setup checklist updated; Testing criteria updated; Module specifications annotated with status |
| 2.1 | January 2026 | Dave Loeffel + Claude | **Architecture refactor:** Introduced three-layer agent architecture; Created [sage-agent-architecture.md](sage-agent-architecture.md); Updated Section 2 (System Architecture), Section 4 (Data Layer), Section 5 (Sub-Agents) to reference architecture doc; Removed duplicated content; Added conversation memory and Indexer/Search Agent concepts |
| 2.2 | January 18, 2026 | Dave Loeffel + Claude | **DataLayerService complete:** Implemented concrete DataLayerService with entity adapters (email, contact, followup, meeting, generic); Created sage_entities Qdrant collection; Added indexed_entities and entity_relationships tables; 21 unit tests passing; Initial commit to GitHub (github.com/DaveLoeffel/sage-app) |

---

## Related Documents

| Document | Purpose |
|----------|---------|
| [sage-agent-architecture.md](sage-agent-architecture.md) | Detailed three-layer architecture, agent specifications, data schemas, implementation guide |
| [sage-implementation-roadmap.md](sage-implementation-roadmap.md) | Session-by-session implementation plan with detailed progress tracking |
| [GitHub Repository](https://github.com/DaveLoeffel/sage-app) | Source code repository |

---

## API Reference (Quick Reference)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check |
| `/api/v1/auth/google` | GET | Initiate Google OAuth |
| `/api/v1/emails` | GET | List cached emails |
| `/api/v1/emails/{id}/draft-reply` | POST | Generate draft reply |
| `/api/v1/followups` | GET, POST | List/create follow-ups |
| `/api/v1/followups/overdue` | GET | Get overdue follow-ups |
| `/api/v1/followups/due-today` | GET | Get today's due items |
| `/api/v1/followups/{id}` | GET, PATCH, DELETE | Manage single follow-up |
| `/api/v1/followups/{id}/complete` | POST | Mark follow-up complete |
| `/api/v1/followups/{id}/cancel` | POST | Cancel follow-up |
| `/api/v1/calendar` | GET | Calendar events |
| `/api/v1/briefings/morning` | POST | Generate morning briefing |
| `/api/v1/briefings/weekly` | POST | Generate weekly review |
| `/api/v1/chat` | POST | Chat with Sage (via Orchestrator) |
| `/api/v1/dashboard/summary` | GET | Dashboard statistics |
| `/api/v1/meetings` | GET | List upcoming meetings |
| `/api/v1/meetings/{id}/prep` | GET | Get meeting preparation |

Full API documentation available at: `http://localhost:8000/docs`

---

*This document defines WHAT Sage does and WHO it serves. For HOW Sage is built (architecture, agents, data flow), see [sage-agent-architecture.md](sage-agent-architecture.md). The system prioritizes the Core Principles: 100% Context, 100% Persistence, 100% Accuracy, and Human-in-the-Loop.*
