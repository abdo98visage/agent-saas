# Production Readiness Test Report

Last updated: 2026-06-15

Purpose: use this document as the main checklist while testing the platform on VPS and real devices. For each item, fill in status, notes, and required fixes.

Status values:

- `Not started`
- `In progress`
- `Passed`
- `Failed`
- `Blocked`

## Target Platform Goal

The platform should run on a VPS with:

- Admin Dashboard for employees, profiles, assignments, API keys, quotas, sessions, KPIs, audit, and Hermes control.
- Employee Desktop App installed on employee PCs.
- Hermes profiles mounted to employees.
- Editable profile files from dashboard: `AGENTS.md`, `skills.md`, `soul.md`, `system_prompt.md`.
- MiniMax as the main provider, with future support for OpenAI-compatible and local providers.
- Telegram connection for employees.
- Full monitoring of usage, cost, failures, sessions, and profile performance.

## Current Baseline

- Local backend tests pass.
- Frontend lint/build pass.
- Docker E2E journey passes with mock Hermes runtime.
- Production deployment still needs real VPS validation.
- Real Hermes runtime still needs compatibility validation.
- Real MiniMax and Telegram flows still need live validation.

## How To Record Test Results

Use this format under each item:

```text
Status:
Date:
Tester:
Environment:
Notes:
Required fixes:
Retest result:
```

---

## 1. VPS Deployment

Goal: prove the platform runs correctly on the target VPS.

Checklist:

- VPS has Docker and Docker Compose installed.
- Domain points to VPS.
- TLS certificates are installed.
- `.env.production` is configured with strong secrets.
- `docker-compose.production.yml` starts all services.
- PostgreSQL migrations run on a fresh database.
- Admin dashboard opens over HTTPS.
- API works over HTTPS.
- WebSocket works over WSS.
- Production smoke test passes.

Command:

```powershell
.\deploy\smoke_test.ps1 -BaseUrl https://your-domain.example -AdminEmail admin@company.com -AdminPassword admin123
```

Test notes:

```text
Status:
Date:
Tester:
Environment:
Notes:
Required fixes:
Retest result:
```

---

## 2. Real Hermes Runtime

Goal: replace mock Hermes with the real runtime and prove the contract works.

Checklist:

- Real Hermes Docker image is configured.
- `GET /health` works.
- `POST /runs` works.
- `POST /runs/stream` works.
- Hermes reads synced profile workspace files.
- `AGENTS.md` is used by Hermes.
- `skills.md` is used by Hermes.
- `soul.md` is used by Hermes.
- `system_prompt.md` is used by Hermes.
- `profile.json` metadata is used or safely ignored.
- Run output returns final content.
- Stream output returns chunks/events.
- Tool/MCP events are persisted in `agent_run_events`.
- Runtime errors are visible in Admin Dashboard.

Test notes:

```text
Status:
Date:
Tester:
Environment:
Notes:
Required fixes:
Retest result:
```

---

## 3. MiniMax Provider And API Keys

Goal: prove real provider key resolution and cost tracking.

Checklist:

- Profile-level MiniMax key works.
- One profile key can serve multiple employees.
- Employee override key wins over profile key.
- Platform fallback key works when no employee/profile key exists.
- Missing provider key returns a clear setup error.
- Full API key is never returned by any API response.
- `spent_today` updates.
- `tokens_used` updates.
- `total_cost` updates.
- KPI updates.
- `AgentRun` cost/tokens update.
- Budget exceeded blocks new requests.

Test notes:

```text
Status:
Date:
Tester:
Environment:
Notes:
Required fixes:
Retest result:
```

---

## 4. Desktop App Release Readiness

Goal: prove employees can install and use the Desktop App safely.

Checklist:

- Windows installer builds successfully.
- Installer works on a clean employee machine.
- Employee activates account using invite token.
- Desktop connects to VPS over WSS.
- Desktop sends chat messages successfully.
- Offline queue stores messages when disconnected.
- Offline queue replays messages after reconnect.
- Project context excludes `.env`, secrets, `.git`, `node_modules`, `venv`, `build`, `dist`.
- Project context sends limited snippets, not full project.
- File edit preview is shown before save.
- File write requires explicit apply/approval.
- `UPDATE_FEED_URL` is configured.
- Manual update check works.
- Auto-update works on a packaged release.
- Code signing plan is defined before external distribution.

Test notes:

```text
Status:
Date:
Tester:
Environment:
Notes:
Required fixes:
Retest result:
```

---

## 5. Telegram Live Flow

Goal: prove Telegram works with activated employees and assigned profiles.

Checklist:

- Bot token is configured.
- Webhook URL is configured on the VPS domain.
- Webhook secret validation works.
- Employee generates bind code from Desktop.
- Employee sends `/bind <code>` to Telegram bot.
- Telegram binding is stored.
- Telegram message reaches backend.
- Message uses the employee assigned profile.
- Response is sent back to Telegram.
- Session is saved.
- Agent run is saved.
- KPI is updated.
- Unactivated employee is rejected.
- Unbound Telegram user is rejected.

Test notes:

```text
Status:
Date:
Tester:
Environment:
Notes:
Required fixes:
Retest result:
```

---

## 6. Observability And KPIs

Goal: Admin can understand health, cost, usage, and failures without terminal access.

Checklist:

- Dashboard shows Hermes health.
- Dashboard shows failed profile syncs.
- Dashboard shows failed runs.
- Dashboard shows total runs today.
- Dashboard shows run failure rate.
- Dashboard shows average latency.
- Dashboard shows profile usage.
- Dashboard shows employee cost.
- Dashboard shows API key budget pressure.
- Alerts exist for API key usage over 70%.
- Alerts exist for API key usage over 90%.
- Profile budget exceeded is visible.
- Employee quota exceeded is visible.
- KPI is not based only on message count.
- Manual task completion or feedback workflow is planned or implemented.

Test notes:

```text
Status:
Date:
Tester:
Environment:
Notes:
Required fixes:
Retest result:
```

---

## 7. Backup And Restore

Goal: prove production data can be recovered.

Checklist:

- Database backup script runs.
- Hermes profiles backup script runs.
- Restore script runs on a clean environment.
- Users are restored.
- Profiles are restored.
- Assignments are restored.
- Sessions/messages are restored.
- API keys remain decryptable with the same `FERNET_KEY`.
- Hermes profile workspaces are restored.
- Platform works after restore.
- Smoke test passes after restore.

Commands:

```powershell
.\deploy\backup.ps1
.\deploy\restore.ps1 -DatabaseBackup .\backups\agentsaas-db-YYYYMMDD-HHMMSS.sql -HermesProfilesBackup .\backups\agentsaas-hermes-profiles-YYYYMMDD-HHMMSS.tar
```

Test notes:

```text
Status:
Date:
Tester:
Environment:
Notes:
Required fixes:
Retest result:
```

---

## 8. Security Hardening

Goal: prove employees cannot access unauthorized data or actions.

Checklist:

- Employee cannot access admin APIs.
- Employee cannot view another employee session.
- Employee cannot use an unassigned profile.
- Disabled employee cannot use chat.
- Disabled profile cannot be used.
- Deleted/disabled assignment blocks profile use.
- Full provider API keys are never exposed.
- Admin lifecycle actions are audited.
- API key create/update/delete/rotate are audited.
- Profile sync actions are audited.
- Employee activation is audited.
- CORS is restricted to production domains.
- `SECRET_KEY` is strong.
- `FERNET_KEY` is strong and backed up securely.
- `POSTGRES_PASSWORD` is strong.
- `HERMES_ORCHESTRATOR_SECRET` is strong.
- PostgreSQL RLS decision is documented: implemented or explicitly deferred with tests.

Test notes:

```text
Status:
Date:
Tester:
Environment:
Notes:
Required fixes:
Retest result:
```

---

## 9. Production Runbook

Goal: deployment and recovery steps are documented enough to repeat safely.

Checklist:

- VPS setup steps are documented.
- `.env.production` setup is documented.
- Secret generation is documented.
- TLS setup is documented.
- Docker compose startup is documented.
- Migration command is documented.
- Admin seed/login flow is documented.
- Hermes install/start flow is documented.
- MiniMax key setup is documented.
- Desktop installer distribution is documented.
- Update feed process is documented.
- Backup process is documented.
- Restore process is documented.
- Rollback process is documented.

Test notes:

```text
Status:
Date:
Tester:
Environment:
Notes:
Required fixes:
Retest result:
```

---

## 10. Documentation Cleanup

Goal: documentation should match the real platform state.

Checklist:

- `CURRENT_STATUS` is updated.
- Old test counts are removed.
- Docker E2E status is documented.
- Real VPS status is documented after testing.
- Real Hermes status is documented after testing.
- Real MiniMax status is documented after testing.
- Real Telegram status is documented after testing.
- Arabic encoding issues are fixed where needed.
- The difference is clear between:
  - implemented
  - locally tested
  - Docker E2E tested
  - VPS tested
  - production-ready

Test notes:

```text
Status:
Date:
Tester:
Environment:
Notes:
Required fixes:
Retest result:
```

---

## Final Go-Live Criteria

The platform is ready for real use only when all are true:

- VPS deployment works over HTTPS/WSS.
- Real Hermes runtime works.
- Real MiniMax key works.
- Desktop installer works on a clean machine.
- Telegram live flow works.
- Backup/restore is verified.
- Admin dashboard shows usage, cost, sessions, failed runs, failed syncs, and key pressure.
- Security isolation tests pass.
- Production runbook is complete.

Final decision:

```text
Status:
Approved by:
Approval date:
Known risks:
Launch scope:
Post-launch monitoring plan:
```
