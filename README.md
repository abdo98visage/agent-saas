# FQ-SaaS — Enterprise AI Agent Platform

Multi-user AI agent platform with complete data isolation, admin control, and quota management.

## Architecture

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

- **Admin user**: `admin@fqsaas.com` / `admin123`
- **4 Agent Templates**: default, it, marketing, hr
