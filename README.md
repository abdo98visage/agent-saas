# FQ-SaaS — Enterprise AI Agent Platform

Multi-user AI agent platform with complete data isolation, admin control, and quota management.

## Architecture

For the Hermes runtime integration roadmap and implementation phases, see
[`docs/EXECUTION PLAN/EXECUTION PLAN.md`](docs/EXECUTION%20PLAN/EXECUTION%20PLAN.md).

```
┌──────────────┐     ┌─────────────┐     ┌──────────────┐
│  Desktop     │────▶│  FastAPI    │────▶│  PostgreSQL  │
│  (Electron)  │     │  Backend    │     │  + Redis     │
└──────────────┘     └─────────────┘     └──────────────┘
                          │
                          ▼
                   ┌─────────────┐
                   │  LLM API    │
                   │ (MiniMax)   │
                   └─────────────┘
```

## Features

- **Multi-user isolation** — Each employee has isolated data via `user_id`
- **JWT authentication** — 8-hour tokens with role-based access
- **Admin dashboard APIs** — Employee CRUD, quota management, KPIs, audit log
- **Agent templates** — YAML-based templates per department (IT, marketing, HR, sales)
- **Model routing** — IT gets powerful models (235B), others get standard (14B)
- **Daily quotas** — Token and request limits per user
- **Audit logging** — All sensitive operations are tracked
- **Telegram gateway** — Webhook-based Telegram bot integration
- **Chat with project context** — Attach local file context to messages

## Quick Start

### Prerequisites

- Python 3.11+
- Docker & Docker Compose
- PostgreSQL 16+ (via Docker)

### Setup

```bash
# 1. Start infrastructure
docker-compose up -d

# 2. Install dependencies
pip install -r requirements.txt

# 3. Run migrations
alembic upgrade head

# 4. Seed default data (templates + admin)
python seed_templates.py

# 5. Run the server
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### Production Stack

`docker-compose.production.yml` runs the admin frontend, FastAPI API, PostgreSQL, Redis, Celery worker/beat, Hermes orchestrator, and nginx HTTPS/WSS reverse proxy.

### Local Docker Validation

Run the full platform locally before moving to a VPS:

```powershell
.\deploy\docker_e2e.ps1 -Rebuild
```

This starts PostgreSQL, Redis, API, admin frontend, Hermes orchestrator, and a local Hermes-compatible runtime inside Docker, then runs the smoke journey end to end.

Before starting production, copy `.env.production.example` to `.env.production`, set strong `SECRET_KEY`, `FERNET_KEY`, `POSTGRES_PASSWORD`, and `HERMES_ORCHESTRATOR_SECRET`, then place TLS files at:

- `deploy/certs/fullchain.pem`
- `deploy/certs/privkey.pem`

The default Docker stack runs the Hermes-compatible runtime as an internal service on the private Docker network and does not mount the host Docker socket.

Deployment templates:

- Current `llama.cpp` / OpenAI-compatible mode: `.env.production.llama.example`
- Final `MiniMax` mode: `.env.production.minimax.example`

Operational docs:

- `docs/SAFE_PRODUCTION_DEPLOY.md`
- `docs/PRODUCTION_DEPLOYMENT_FINAL.md`
- `docs/RELEASE_CHECKLIST.md`
- `docs/DESKTOP_RELEASE_RUNBOOK.md`

Start production with the env file explicitly:

```powershell
.\deploy\production_readiness_check.ps1
docker compose --env-file .env.production -f docker-compose.production.yml up -d --build
```

Operational scripts:

```powershell
.\deploy\backup.ps1
.\deploy\restore.ps1 -DatabaseBackup .\backups\agentsaas-db-YYYYMMDD-HHMMSS.sql -HermesProfilesBackup .\backups\agentsaas-hermes-profiles-YYYYMMDD-HHMMSS.tar
.\deploy\smoke_test.ps1 -BaseUrl https://your-domain.example -AdminEmail admin@company.com -AdminPassword your-password
```

### Desktop Build

The desktop app reads its default API URL from `desktop/desktop-config.json`. For local Docker testing it defaults to `http://localhost:8002/api`. Before building a VPS release, set that file to your public API URL, for example `https://your-domain.example/api`, then run:

```powershell
cd desktop
npm run build
```

For production-style release packaging with an optional generic update feed, set `UPDATE_FEED_URL` before building. If it is omitted, the desktop app still builds, but update checks remain unconfigured.

For the full Windows release checklist including signing and update-feed preflight, see:

- `docs/DESKTOP_RELEASE_RUNBOOK.md`

### Configure

Copy `.env.example` to `.env` and set your values:

```bash
APP_NAME=FQ-SaaS
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/fqsaas
REDIS_URL=redis://localhost:6379/0
LLM_PROVIDER=minimax
MINIMAX_API_KEY=your-key-here
MINIMAX_BASE_URL=https://api.minimax.chat/v1/chat/completions
SECRET_KEY=your-jwt-secret-key
```

OpenAI-compatible local provider example for `llama.cpp`:

```bash
LLM_PROVIDER=openai
OPENAI_API_KEY=local-llama
OPENAI_BASE_URL=http://your-llama-host:54175/v1/chat/completions
```

Recommended usage:

- Local/staging validation now: `LLM_PROVIDER=openai` with `OPENAI_BASE_URL` pointed at your OpenAI-compatible `llama.cpp` endpoint.
- Production later: switch to `LLM_PROVIDER=minimax` with a real `MINIMAX_API_KEY`.

Optional backend observability:

```bash
SENTRY_DSN=your-sentry-dsn
SENTRY_ENVIRONMENT=production
SENTRY_TRACES_SAMPLE_RATE=0.1
```

## API Endpoints

### Auth
| Method | Path | Description |
|--------|------|-------------|
| POST | /api/auth/register | Register new user |
| POST | /api/auth/login | Login and get JWT |
| GET | /api/auth/me | Get current user profile |

### Chat
| Method | Path | Description |
|--------|------|-------------|
| POST | /api/chat/message | Send message to agent |
| GET | /api/chat/conversations | List user conversations |
| GET | /api/chat/conversations/{id}/messages | Get conversation messages |

### Admin (role=admin required)
| Method | Path | Description |
|--------|------|-------------|
| GET | /api/admin/employees | List all employees |
| POST | /api/admin/employees | Create employee |
| PUT | /api/admin/employees/{id} | Update employee |
| DELETE | /api/admin/employees/{id} | Disable employee |
| PUT | /api/admin/employees/{id}/quotas | Set daily limits |
| GET | /api/admin/kpis | Get KPI data |
| GET | /api/admin/audit-log | Get audit trail |
| GET | /api/admin/agent-templates | List agent templates |

### Telegram
| Method | Path | Description |
|--------|------|-------------|
| POST | /api/telegram/webhook | Telegram webhook handler |

## Project Structure

```
app/
├── main.py                    # FastAPI app entry point
├── core/
│   ├── config.py              # Settings (LLM, JWT, DB)
│   ├── db.py                  # AsyncPostgreSQL engine + session
│   └── security.py            # JWT create/decode + bcrypt
├── models/                    # SQLAlchemy models
│   ├── user.py                # users (department, role, quotas)
│   ├── session.py             # sessions (conversations per user)
│   ├── message.py             # messages (with project_context)
│   ├── agent_template.py      # agent_templates (YAML-based)
│   ├── telegram_binding.py    # telegram_bindings
│   ├── audit_log.py           # audit_log
│   └── kpi.py                 # kpis
├── schemas/                   # Pydantic validation
│   ├── auth.py                # Login, Register, Token
│   ├── user.py                # User CRUD schemas
│   ├── chat.py                # Chat message schemas
│   └── admin.py               # Admin response schemas
├── api/                       # Route routers
│   ├── health.py              # Health check
│   ├── auth.py                # Auth endpoints + JWT dependency
│   ├── chat.py                # Chat endpoints
│   ├── admin.py               # Admin CRUD endpoints
│   └── telegram.py            # Telegram webhook
└── services/
    ├── agent_service.py       # LLM caller + model routing
    ├── token_tracker.py       # Quota checking
    └── audit_service.py       # Audit logging
```

## Database Schema

| Table | Description |
|-------|-------------|
| users | Employee accounts with department, role, quotas |
| sessions | Conversations linked to users |
| messages | Chat messages with optional project context |
| agent_templates | Department-specific agent configurations |
| telegram_bindings | User ↔ Telegram account links |
| audit_log | Immutable log of admin actions |
| kpis | Per-user daily performance metrics |

## LLM Providers

Supports multiple providers via `LLM_PROVIDER` env variable:

| Provider | Config |
|----------|--------|
| mock | No API key needed (testing) |
| minimax | `MINIMAX_API_KEY`, `MINIMAX_BASE_URL` |
| openai | `OPENAI_API_KEY` |
| ollama | `OLLAMA_BASE_URL`, `DEFAULT_MODEL` |

## Security

- bcrypt (12 rounds) for password hashing
- JWT tokens with 8-hour expiry
- Role-based access (admin vs employee)
- Per-user data isolation (all queries filtered by user_id)
- Audit log for all admin actions
- Daily token/request quotas per user
- Webhook secret validation for Telegram

## Testing

```bash
# Run with mock provider for testing
export LLM_PROVIDER=mock
uvicorn app.main:app --reload
```

## Default Seed Data

Running `seed_templates.py` creates:

- **Admin user**: `admin@company.com` / `admin123`
- **4 Agent Templates**: default, it, marketing, hr
