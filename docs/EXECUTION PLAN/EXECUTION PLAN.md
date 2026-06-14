# Execution Plan: Mount Hermes Agent Runtime Into AgentSaaS

## Current State

AgentSaaS already has the SaaS control-plane pieces: admin users, employees, profiles, assignments, API keys, quotas, sessions, KPIs, Telegram, and desktop connectivity. Before this Hermes layer, profile content was only composed into prompts and sent directly to MiniMax/OpenAI/Ollama from FastAPI.

The target architecture keeps FastAPI as the control plane and mounts Hermes as a separate Docker-managed execution runtime on the VPS.

```text
Admin Dashboard
      |
      v
FastAPI Control Plane
auth, employees, profiles, assignments, keys, quotas, sessions, KPIs, audit
      |
      v
Hermes Runtime Adapter
      |
      v
Hermes Orchestrator + Hermes Docker Service
profile workspaces, AGENTS.md, skills.md, soul.md, MCP/tools, agent execution
```

## Admin Zero-Terminal Workflow

1. Deploy the platform on a VPS.
2. Admin opens the dashboard and checks Hermes Runtime.
3. If Hermes is not installed, admin clicks Install.
4. Admin starts or restarts Hermes from the dashboard.
5. Admin creates Hermes profiles such as marketing or accounting.
6. Profile creation syncs `AGENTS.md`, `skills.md`, `soul.md`, `system_prompt.md`, and metadata into Hermes.
7. Admin adds profile-level MiniMax/API keys by default.
8. Admin creates employees and mounts one or more profiles to each employee.
9. Employee messages enter FastAPI through desktop, web, Telegram, or WebSocket.
10. FastAPI validates auth, assignment, active status, keys, and quotas, then dispatches Hermes profiles to Hermes.
11. Admin reviews sessions, run events, tokens, cost, failures, KPIs, and profile usage in the dashboard.

## API Key Ownership Policy

Default key model: profile-level keys.

Resolution order:

1. Employee override key.
2. Profile key.
3. Platform fallback key.
4. Reject request with a clear setup error.

This lets one marketing profile serve many employees while still allowing employee-specific keys for exceptions.

## Implementation Phases

### Phase 1: Runtime Boundary

- Add runtime abstraction: direct LLM and Hermes runtime.
- Keep current provider behavior available as `direct_llm`.
- Add profile runtime metadata and sync status.
- Persist agent runs and run events.

### Phase 2: Hermes Orchestrator

- Add internal orchestrator client.
- Add dashboard lifecycle endpoints: status, install, start, restart, stop, repair sync, logs.
- Keep Docker/service privileges outside FastAPI.
- Audit every lifecycle action.

### Phase 3: Profile Sync

- Map SaaS profiles to Hermes workspaces.
- Generate `AGENTS.md`, `skills.md`, `soul.md`, `system_prompt.md`, and profile metadata.
- Sync profiles on create/update/repair.
- Block Hermes execution until a profile is synced.

### Phase 4: Profile-First API Keys

- Generalize keys to `user`, `profile`, and `platform` owners.
- Keep employee keys as overrides.
- Encrypt all keys and never expose full values after save.

### Phase 5: Hermes Execution

- Route synced Hermes profiles through the Hermes runtime adapter.
- Stream events through existing chat/WebSocket flows.
- Persist messages, runs, events, tokens, cost, tools, MCP server usage, and failures.

### Phase 6: KPI And Dashboard Visibility

- Surface Hermes health, failed syncs, failed runs, cost, profile usage, and decision-maker metrics.
- Add run/event details to admin session history.

### Phase 7: Production Hardening

- Add production compose/nginx/HTTPS/WSS deployment assets.
- Validate backup/restore.
- Add VPS smoke tests for dashboard login, Hermes install, profile sync, assignment, and one successful run.

## Test Plan

- Runtime router chooses Hermes for Hermes profiles and direct LLM for fallback profiles.
- Profile sync payload includes `AGENTS.md`, `skills.md`, `soul.md`, metadata, limits, tools, and MCP settings.
- API key resolution follows employee override, profile key, then platform fallback.
- Unassigned or inactive profiles cannot be used.
- Unsynced Hermes profiles cannot run.
- Admin Hermes lifecycle endpoints require admin auth and audit actions.
- Profile create/update records sync status.
- Hermes run success persists messages, run, events, tokens, and cost.
- Hermes run failure persists failed run metadata.
- Frontend builds with Hermes Runtime page, API key owner types, profile sync status, and assignment health.

## Assumptions

- Hermes Agent can run as a Docker service on the same VPS.
- Hermes is controlled through an internal orchestrator API.
- FastAPI remains the source of truth for tenant authorization, quotas, cost controls, and audit.
- Hermes is trusted as the execution engine, not as the business policy owner.
- Desktop app can continue using the existing API/WebSocket contract.
