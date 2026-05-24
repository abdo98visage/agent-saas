# AgentSaaS

**AI Agent SaaS Platform** - Config-driven, multi-tenant business agents built with FastAPI + Supabase.

## Architecture

```
┌─────────────┐
│   Frontend   │  (Next.js - future)
└──────┬──────┘
       │
┌──────▼──────┐
│   FastAPI   │  ← This codebase
└──────┬──────┘
       │
  ┌────┴────┐
  ▼         ▼
Supabase   OpenAI
```

## Core Principles

- **One Agent Platform** - All agents share the same engine
- **Config-Driven** - Agents, prompts, tools stored in DB
- **Multi-Tenant** - Every table has `organization_id`
- **Simple First** - No premature optimization

## Project Structure

```
AgentSaaS/
├── app/
│   ├── api/             # FastAPI route handlers
│   │   ├── health.py
│   │   ├── auth.py
│   │   ├── agents.py
│   │   ├── chat.py
│   │   └── documents.py
│   ├── agents/          # Agent runtime engine
│   │   └── engine.py
│   ├── services/        # Business logic
│   │   ├── auth.py
│   │   ├── memory.py
│   │   ├── logger.py
│   │   └── token_tracker.py
│   ├── tools/           # Tool implementations
│   │   ├── base.py
│   │   ├── web_search.py
│   │   ├── competitor_analyzer.py
│   │   ├── ad_copy_generator.py
│   │   ├── crm_lead_saver.py
│   │   └── proposal_generator.py
│   ├── core/            # Core config & DB client
│   │   ├── config.py
│   │   └── db.py
│   ├── models/          # Pydantic models
│   ├── schemas/         # Request/response schemas
│   └── main.py          # Application entry point
├── migrations/          # SQL migrations for Supabase
├── PLAN.md              # Full architecture plan
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── .env.example
```

## Quick Start

### 1. Set up Supabase

1. Create a project at [supabase.com](https://supabase.com)
2. Copy the SQL from `migrations/001_initial_schema.sql`
3. Run it in the Supabase SQL Editor

### 2. Configure Environment

```bash
cp .env.example .env
# Edit .env with your Supabase and OpenAI keys
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Run

```bash
python -m app.main
# or
uvicorn app.main:app --reload
```

Server runs at `http://localhost:8000`

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/health` | Health check |
| GET | `/api/status` | Platform status |
| POST | `/api/auth/register` | Register new user |
| GET | `/api/agents/` | List all agents |
| GET | `/api/agents/{slug}` | Get agent details |
| POST | `/api/chat/message` | Send message to agent |
| GET | `/api/chat/conversations/{id}/messages` | Get messages |
| POST | `/api/documents/upload` | Upload document |

## Current Agents

| Agent | Slug | Purpose |
|-------|------|---------|
| Marketing Agent | `marketing` | Campaigns, ad copy, content calendars |
| Sales Agent | `sales` | Leads, proposals, follow-ups |
| SEO Agent | `seo` | Content optimization, keywords |
| Support Agent | `support` | Customer service responses |

## Deployment

```bash
docker build -t agentsaas .
docker run -p 8000:8000 --env-file .env agentsaas
```

## Development Roadmap

- [x] **Step 1:** Core SaaS Foundation (this phase)
- [ ] **Step 2:** Marketing Agent with real tools
- [ ] **Step 3:** Sales Agent
- [ ] **Step 4:** WhatsApp Integration
- [ ] **Step 5:** Document Intelligence
- [ ] **Step 6:** Team Collaboration
- [ ] **Step 7:** Enterprise APIs
