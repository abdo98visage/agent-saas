# Remaining Work Plan

Last updated: 2026-06-15

## Current Validation Baseline

- Local backend tests pass.
- Frontend lint and production build pass.
- Docker E2E journey passes with the mock Hermes runtime:
  - API health
  - admin login
  - Hermes status
  - Hermes profile creation and sync
  - profile-level provider key
  - employee creation
  - profile assignment
  - employee activation
  - chat through Hermes runtime
  - admin session/run inspection
  - KPI and dashboard observability checks

Run locally:

```powershell
.\deploy\docker_e2e.ps1 -Rebuild
```

Run against VPS:

```powershell
.\deploy\smoke_test.ps1 -BaseUrl https://your-domain.example -AdminEmail admin@company.com -AdminPassword admin123
```

## Remaining Critical Work

1. Real VPS deployment validation
   - Deploy `docker-compose.production.yml` on the target VPS.
   - Configure real TLS certificates.
   - Run Alembic migrations against a fresh PostgreSQL volume.
   - Run the full smoke journey against the public HTTPS domain.

2. Real Hermes runtime compatibility
   - Replace the Docker E2E mock runtime with the real Hermes image.
   - Verify `/health`, `/runs`, and `/runs/stream` contracts.
   - Confirm synced profile workspaces are consumed by Hermes.
   - Validate tool/MCP event payloads are persisted as `agent_run_events`.

3. Real MiniMax provider validation
   - Add a real profile-level MiniMax key.
   - Validate profile key sharing across multiple employees.
   - Validate employee override keys.
   - Validate platform fallback keys.
   - Confirm budget and spent counters update correctly.

4. Telegram production path
   - Configure bot token and webhook URL.
   - Bind an activated employee.
   - Send a Telegram message through the assigned profile.
   - Confirm session, run, KPI, and audit records.

5. Desktop release readiness
   - Build the Windows installer.
   - Validate activation from invite token.
   - Validate WebSocket reconnect and offline queue replay.
   - Configure a real `UPDATE_FEED_URL`.
   - Test manual update check and auto-update install.
   - Add code signing before external distribution.

6. Security hardening
   - Add deeper endpoint isolation tests for admin/chat/session/profile/key flows.
   - Decide whether PostgreSQL RLS is required for launch or explicitly deferred.
   - Validate that full provider keys never leave backend responses.
   - Add production CORS/domain review.

7. Production operations
   - Run backup and restore scripts on the VPS.
   - Add deployment runbook with rollback steps.
   - Add monitoring for failed syncs, failed runs, API key pressure, latency, and Hermes health.

## Recommended Execution Order

1. VPS dry run with mock Hermes using the Docker E2E path.
2. VPS run with real Hermes image.
3. Real MiniMax key and cost controls.
4. Desktop installer and update feed.
5. Telegram live flow.
6. Backup/restore and production runbook.
7. Security hardening pass.
