# Sage - AI Executive Assistant

Sage is a personal AI executive assistant designed for busy executives. It provides intelligent email management, bulletproof follow-up tracking, calendar integration, and proactive briefings powered by Claude AI.

## Features

- **Email Management**: AI-powered email categorization, prioritization, and summarization
- **Follow-up Tracking**: Never let an email fall through the cracks with automated Day 2 reminders and Day 7 escalations
- **Draft Replies**: AI-generated email drafts matching your communication style
- **Morning Briefings**: Daily summaries with priorities, overdue items, and calendar context
- **Meeting Prep**: Context gathering before meetings with email history and past meeting notes
- **Chat Interface**: Natural language queries about your emails, calendar, and tasks

## Architecture

| Component | Technology |
|-----------|------------|
| AI Brain | Claude API (Anthropic) |
| Backend | Python 3.12+ / FastAPI |
| Frontend | Next.js 15 / TailwindCSS |
| Database | PostgreSQL 16 |
| Vector DB | Qdrant |
| Cache | Redis 7 |
| Hosting | Docker Compose |
| Remote Access | Cloudflare Tunnel |

## Quick Start

### Prerequisites

- Docker & Docker Compose
- Google Cloud Console account (for OAuth)
- Anthropic API key

### Setup

1. **Clone and navigate to the project**
   ```bash
   cd sage
   ```

2. **Run the setup script**
   ```bash
   ./scripts/setup.sh
   ```

3. **Configure environment variables**

   Edit `.env` and add your API keys:
   ```bash
   ANTHROPIC_API_KEY=your-anthropic-api-key
   GOOGLE_CLIENT_ID=your-google-client-id.apps.googleusercontent.com
   GOOGLE_CLIENT_SECRET=your-google-client-secret
   ```

4. **Configure Google OAuth**
   - Go to [Google Cloud Console](https://console.cloud.google.com/)
   - Create a new project or select existing
   - Enable Gmail API, Google Calendar API, and Google Drive API
   - Create OAuth 2.0 credentials
   - Add `http://localhost:8000/api/v1/auth/google/callback` as redirect URI

5. **Start the application**
   ```bash
   make dev
   ```

6. **Access the application**
   - Frontend: http://localhost:3000
   - Backend API: http://localhost:8000
   - API Docs: http://localhost:8000/docs

## Project Structure

```
sage/
├── docker-compose.yml      # Container orchestration
├── .env.example            # Environment template
├── Makefile               # Common commands
│
├── backend/
│   ├── Dockerfile
│   ├── pyproject.toml     # Python dependencies
│   ├── alembic/           # Database migrations
│   └── sage/
│       ├── main.py        # FastAPI entry point
│       ├── config.py      # Settings
│       ├── api/           # REST endpoints
│       ├── core/          # Business logic
│       ├── mcp/           # Custom MCP servers
│       ├── models/        # SQLAlchemy models
│       ├── schemas/       # Pydantic schemas
│       ├── services/      # External services
│       └── scheduler/     # Background jobs
│
├── frontend/
│   ├── Dockerfile
│   ├── package.json
│   └── src/
│       ├── app/           # Next.js pages
│       ├── components/    # React components
│       └── lib/           # Utilities & API client
│
└── scripts/
    ├── setup.sh           # Initial setup
    └── backup.sh          # Backup utility
```

## Available Commands

```bash
make dev        # Start all services (foreground)
make up         # Start all services (background)
make down       # Stop all services
make logs       # View logs
make build      # Rebuild containers
make migrate    # Run database migrations
make test       # Run tests
make clean      # Remove all containers and volumes
make prod       # Start with Cloudflare tunnel
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/auth/google` | GET | Initiate OAuth |
| `/api/v1/emails` | GET | List emails |
| `/api/v1/emails/{id}/draft-reply` | POST | Generate AI draft |
| `/api/v1/followups` | GET/POST | Manage follow-ups |
| `/api/v1/followups/overdue` | GET | Overdue items |
| `/api/v1/briefings/morning` | POST | Generate briefing |
| `/api/v1/chat` | POST | Ad-hoc AI query |
| `/api/v1/dashboard/summary` | GET | Dashboard data |

## Follow-up Workflow

1. **Email arrives** → AI analyzes and categorizes
2. **Requires response?** → Auto-create follow-up with due date
3. **Day 2** → Generate reminder email draft
4. **Day 7** → Escalate with supervisor CC (if configured)
5. **Reply detected** → Auto-close follow-up

## MCP Servers

Sage uses Model Context Protocol (MCP) servers for integrations:

- **Google Workspace**: Gmail, Calendar, Drive access
- **Fireflies**: Meeting transcripts (custom server)
- **Entrata**: Property report parsing (custom server)
- **Alpha Vantage**: Stock prices (optional)
- **Memory**: Persistent knowledge graph (optional)

## Remote Access

For accessing Sage from outside your network:

1. Create a Cloudflare Tunnel
2. Add `CLOUDFLARE_TUNNEL_TOKEN` to `.env`
3. Run `make prod`

## Backup & Restore

```bash
# Create backup
./scripts/backup.sh

# Restore PostgreSQL
gunzip -c backups/postgres_TIMESTAMP.sql.gz | docker-compose exec -T postgres psql -U sage sage
```

## Development

### Backend Development

```bash
# Install dependencies
cd backend
pip install -e ".[dev]"

# Run tests
pytest

# Run linting
ruff check sage
```

### Frontend Development

```bash
# Install dependencies
cd frontend
npm install

# Run development server
npm run dev
```

## Configuration

Key configuration options in `.env`:

| Variable | Description |
|----------|-------------|
| `ANTHROPIC_API_KEY` | Claude API key |
| `GOOGLE_CLIENT_ID` | Google OAuth client ID |
| `GOOGLE_CLIENT_SECRET` | Google OAuth secret |
| `EMAIL_SYNC_INTERVAL_MINUTES` | Email sync frequency (default: 5) |
| `FOLLOWUP_REMINDER_DAYS` | Days before reminder (default: 2) |
| `FOLLOWUP_ESCALATION_DAYS` | Days before escalation (default: 7) |
| `MORNING_BRIEFING_HOUR` | Briefing time hour (default: 6) |
| `TIMEZONE` | User timezone (default: America/New_York) |

## License

Private - All rights reserved.
