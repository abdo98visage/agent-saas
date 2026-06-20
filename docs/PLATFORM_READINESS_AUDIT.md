# Platform Readiness Audit

Date: 2026-06-15

## Executive verdict

The platform is materially closer to production readiness after the 2026-06-15 hardening pass, but final 100% release approval still requires a live staging VPS validation with real secrets, real Hermes runtime, real Telegram bot, TLS/domain, backups, and monitoring.

The current codebase now includes fixes for the highest-risk deploy blockers that can be solved locally: production frontend API routing, production migrations at startup, stricter production secret validation, real Telegram Bot API replies from the webhook, Redis-backed rate limiting, Nginx security headers, desktop dependency upgrades, and production readiness preflight checks.

Recommended decision:

- Deploy first to a staging VPS with production-like secrets, domain, TLS, real Hermes runtime, Telegram webhook, and load/backup testing.
- Promote to production only after the final readiness gate at the end of this document passes on the VPS.

## 2026-06-15 hardening update

Completed:

- Frontend API client now defaults to relative `/api` instead of `http://localhost:8000/api`.
- Frontend Docker build accepts `NEXT_PUBLIC_API_URL`, defaulting to `/api`.
- Production compose now runs `alembic upgrade head` before starting the API.
- Production compose now waits for healthy DB/Redis/orchestrator services where supported.
- The default Docker stack now runs a platform-owned Hermes-compatible runtime service without mounting the host Docker socket.
- Nginx now includes HSTS, CSP, frame, content-type, referrer, and permissions hardening headers.
- Production settings now reject weak/default secrets, invalid Fernet keys, wildcard CORS, mock LLM provider, and missing provider keys in production.
- Telegram webhook now sends replies via Telegram Bot API instead of only returning JSON to Telegram.
- Telegram temporary bind-code flow now returns the existing unbound code instead of incorrectly reporting an already-bound account.
- Rate limiting now uses Redis when available, with in-memory fallback for local development.
- WebSocket messages now have a configurable max payload size.
- Added `deploy/production_readiness_check.ps1` to fail fast on unsafe `.env.production` values and missing production compose safeguards.
- Frontend dependency audit now passes after forcing safe PostCSS resolution.
- Desktop dependencies were upgraded to Electron 42.4.0 and Electron Builder 26.15.3; desktop audit now passes.
- Desktop packaging build now passes locally without requiring `UPDATE_FEED_URL`.

Latest local validation:

- Backend tests: `104 passed`.
- Frontend lint: passed.
- Frontend build: passed.
- Frontend audit: `0 vulnerabilities`.
- Desktop audit: `0 vulnerabilities`.
- Desktop build: passed.

Blocked local validation:

- Docker E2E could not be rerun in the current machine because the Docker daemon was unavailable: `dockerDesktopLinuxEngine` pipe was missing. The E2E script now fails fast when Docker is not running.

## Validation already performed

- Backend test suite: `101 passed`.
- Frontend lint: passed.
- Frontend production build: passed.
- Docker E2E journey with local Hermes-compatible runtime: passed.
- Frontend dependency audit: failed with moderate vulnerabilities through `next` / `postcss`.
- Desktop dependency audit: failed with high vulnerabilities through Electron and Electron Builder dependency chain.

Important limitation:

The Docker E2E journey proves the platform contract and main user journey with the local Hermes-compatible runtime. It does not prove a third-party Hermes image, real LLM provider, real Telegram bot, or real production VPS network path are fully working.

## Readiness matrix

| Area | Readiness | Status | Main reason |
| --- | ---: | --- | --- |
| Backend API core | 75% | Needs hardening | Tests pass, but production migration, real provider, quotas, and security gates still need work. |
| Admin frontend | 85% | Needs VPS verification | Build/lint/audit pass and API URL fallback is fixed; verify public-domain browser requests on VPS. |
| Hermes orchestration | 75% | Needs VPS verification | The local Docker runtime contract passes without Docker socket exposure; the VPS network path must still pass. |
| Telegram integration | 75% | Needs live bot verification | Webhook now sends replies through Telegram Bot API; must verify with real bot token/webhook. |
| Desktop app | 75% | Needs signing/update validation | Audit/build pass; code signing and real update feed remain release-environment tasks. |
| Deployment/VPS | 70% | Needs staging execution | Compose now has migrations, health waits, headers, and preflight; backups and real VPS checks remain. |
| Observability/KPIs | 60% | Needs hardening | Internal KPIs exist, but alerting, dashboards, log aggregation, and SLO checks are not production-ready. |
| Security | 55% | Needs hardening | Basic auth/encryption exist, but token storage, WebSocket tokens, Docker socket exposure, headers, and dependency vulnerabilities need fixes. |
| Scaling | 50% | Needs architecture work | Redis/Celery/Postgres exist, but rate limiting, WebSocket state, worker sizing, and load tests need production design. |
| Maintainability | 70% | Acceptable but needs cleanup | Code is modular enough, but large modules and source-inspection tests make future changes riskier. |

## Critical release blockers

### 1. Admin frontend production API URL can point to localhost

Status: fixed locally; verify on VPS.

Files:

- `frontend/src/lib/api/client.ts`
- `frontend/Dockerfile`
- `docker-compose.production.yml`

Problem:

Previously, the frontend client fell back to `http://localhost:8000/api`. In a production browser, `localhost` means the user's machine, not the VPS.

Risk:

The admin dashboard can load but fail all API requests after deployment.

Implemented fix:

- Browser calls default to relative `/api`.
- `NEXT_PUBLIC_API_URL` is passed as a Docker build argument with `/api` default.

Acceptance test:

- Build the production image.
- Open the admin dashboard through the VPS domain.
- Confirm browser network requests go to `https://your-domain/api/...`, not `localhost`.

### 2. Production Hermes orchestrator Docker lifecycle is not fully proven

Status: partially fixed locally; real VPS verification required.

Files:

- `app/hermes_orchestrator_app.py`
- `docker-compose.production.yml`
- `Dockerfile`

Problem:

The old production design mounted `/var/run/docker.sock` and relied on Docker lifecycle control from inside the orchestrator.

Risk:

The production orchestrator may report failures when trying to start/stop/restart the real Hermes runtime container.

Implemented fix:

- The default production compose now runs `hermes-runtime` as a private Compose service.
- The orchestrator talks to it over the internal Docker network with `HERMES_MANAGED_EXTERNALLY=true`.
- The default compose no longer mounts `/var/run/docker.sock`.

Remaining requirement:

- Add a production-like VPS test that exercises real start/stop/restart/status against the actual Hermes runtime container.

Acceptance test:

- On staging VPS, call Hermes status, start, restart, stop, and status again.
- Confirm the real container changes state and the admin UI reflects it.

### 3. Real Hermes runtime is not validated end-to-end

Files:

- `app/services/hermes_client.py`
- `app/services/agent_service.py`
- `app/api/websocket_chat.py`
- `app/api/admin.py`

Problem:

The current E2E journey validates the platform using the local Hermes-compatible runtime, not an external third-party Hermes image.

Risk:

Real provider errors, streaming differences, auth headers, timeout behavior, token accounting, and output shape mismatches can appear only after deployment.

Required fix:

- Add a staging E2E journey against the real Hermes runtime.
- Validate normal chat, streaming chat, timeout, provider error, and budget exceeded paths.

Acceptance test:

- A real employee can chat from the admin/frontend journey.
- The run appears in admin sessions, usage, cost, KPIs, and failure-rate metrics.

### 4. Telegram webhook does not complete the live reply flow

Status: fixed locally; live Telegram verification required.

Files:

- `app/api/telegram.py`

Problem:

The webhook endpoint parses Telegram updates and returns a JSON response, but it does not clearly call Telegram Bot API `sendMessage` inside the webhook path.

Risk:

Telegram users may send a message and receive no reply, even though the backend processed the request.

Implemented fix:

- Webhook now sends the generated response back through Telegram Bot API.
- Delivery status is included in the webhook result for observability.

Acceptance test:

- Send a message from a real Telegram account.
- Receive a real reply in Telegram.
- Confirm the conversation and run are recorded in the admin dashboard.

### 5. Production migrations are not part of startup/release flow

Status: fixed locally.

Files:

- `docker-compose.production.yml`
- `alembic/`

Problem:

The production API starts Uvicorn directly. There is no explicit release step for `alembic upgrade head` before the app serves traffic.

Risk:

Production containers may boot against an outdated schema and fail at runtime.

Implemented fix:

- Production API command runs `alembic upgrade head` before Uvicorn.
- Migration failure stops API startup.

Acceptance test:

- Start from an empty staging database.
- Run the production deployment.
- Confirm all migrations apply and the app becomes healthy only after schema readiness.

### 6. Dependency vulnerabilities block release confidence

Status: fixed locally.

Files:

- `frontend/package.json`
- `frontend/package-lock.json`
- `desktop/package.json`
- `desktop/package-lock.json`

Problem:

Frontend audit reports moderate vulnerabilities in the Next/PostCSS chain. Desktop audit reports high vulnerabilities in Electron and Electron Builder dependency chains.

Risk:

Known vulnerabilities remain in shipped artifacts, especially the desktop app.

Implemented fix:

- Frontend uses a PostCSS override pinned to `8.5.10`.
- Desktop Electron/Electron Builder were upgraded.
- Frontend and desktop audits now report `0 vulnerabilities`.

Acceptance test:

- `npm audit --audit-level=moderate` passes for frontend.
- `npm audit --audit-level=high` passes for desktop or documented exceptions are approved.
- Desktop package builds and launches after upgrades.

### 7. Desktop release is not distribution-ready

Status: partially fixed locally; release signing/update feed verification remains.

Files:

- `desktop/electron-builder.yml`
- `desktop/src/main/main.js`
- `desktop/src/preload/preload.js`

Problem:

The desktop app has update readiness UI and IPC, but release signing and full update-feed validation are not complete. Config currently has signing disabled.

Risk:

Users may see operating system warnings, update checks may fail, and tamper-resistance is weak.

Implemented fix:

- Desktop audit passes.
- Desktop package build passes locally.
- Update IPC/UI remains present.

Remaining requirement:

- Configure production code signing and update feed credentials.
- Install, launch, update, and rollback-test on a clean Windows VM.

Acceptance test:

- Signed installer installs cleanly on Windows.
- Update check reports current version.
- A newer test version updates successfully.

## Important security issues

### 8. WebSocket authentication uses query-string token

Files:

- `app/api/websocket_chat.py`

Problem:

The WebSocket endpoint accepts token in the query string.

Risk:

Tokens can leak into logs, browser history, reverse proxy logs, and monitoring tools.

Required fix:

- Use short-lived WebSocket session tokens, generated through an authenticated HTTP endpoint.
- Keep the token valid for seconds/minutes and single purpose.
- Redact query strings in Nginx/app logs.

Acceptance test:

- WebSocket connection works with a short-lived token.
- Expired/reused tokens fail.
- Logs do not expose bearer tokens.

### 9. Frontend session storage

Files:

- `frontend/src/components/auth-provider.tsx`

Problem:

Previously, JWT access tokens were stored in `localStorage`.

Risk:

Any XSS vulnerability can steal long-lived admin tokens.

Implemented fix:

- Admin web login now receives an HttpOnly, SameSite cookie.
- The frontend validates sessions through `/api/auth/me` instead of reading `localStorage`.
- Bearer token responses remain for desktop compatibility.

Acceptance test:

- Login works without exposing access token to JavaScript, or token exposure is explicitly accepted with compensating controls.

### 10. Docker socket exposure was removed from the default stack

Files:

- `docker-compose.production.yml`

Problem:

The old orchestrator design mounted `/var/run/docker.sock`.

Risk:

Compromise of the orchestrator can become host-level compromise.

Implemented fix:

- The default production compose runs a private `hermes-runtime` service.
- The orchestrator no longer needs host Docker socket access for the default Docker path.

Acceptance test:

- Threat model is documented.
- Orchestrator network and host privileges are intentionally constrained.

### 11. Production secret validation is incomplete

Files:

- `app/core/config.py`

Problem:

The app validates some default secrets but does not fully enforce all production invariants, including orchestrator secret strength and provider configuration.

Risk:

A production deployment can boot with weak or missing sensitive settings.

Required fix:

- Validate `SECRET_KEY`, `FERNET_KEY`, `POSTGRES_PASSWORD`, `HERMES_ORCHESTRATOR_SECRET`, provider API keys, CORS origins, and public URLs when `ENVIRONMENT=production`.

Acceptance test:

- App refuses to start with weak/missing production secrets.
- App starts with valid staging secrets.

### 12. Nginx security headers are incomplete

Files:

- `deploy/nginx.conf`

Problem:

TLS proxying exists, but common hardening headers are missing or incomplete.

Required fix:

- Add HSTS after HTTPS is confirmed.
- Add `X-Frame-Options`, `X-Content-Type-Options`, `Referrer-Policy`, and a production CSP.
- Ensure WebSocket upgrade headers remain correct.

Acceptance test:

- Security header scan passes the agreed baseline.
- Admin UI still works with CSP enabled.

## Scaling and architecture concerns

### 13. Rate limiting is not Redis-backed

Problem:

If rate limiting is process-local or IP-local, it does not scale across multiple API replicas.

Risk:

Limits can be bypassed by multi-process deployment or container restarts.

Required fix:

- Move rate limiting counters to Redis.
- Use user/profile/API-key dimensions, not only IP.

Acceptance test:

- Two API replicas share the same limit state.

### 14. WebSocket state is not horizontally scalable yet

Problem:

Live WebSocket connections are process-bound.

Risk:

Multiple API replicas behind a load balancer can break session continuity unless sticky sessions or a pub/sub layer is used.

Required fix:

- Start with one API WebSocket replica plus sticky sessions, or add Redis pub/sub for cross-replica events.

Acceptance test:

- Load-balanced WebSocket sessions stay connected during normal traffic.

### 15. Token and cost accounting are approximate

Problem:

Profile limits and cost metrics do not fully prove provider-reported input/output token usage across all paths.

Risk:

Budget limits can be inaccurate, especially for expensive provider calls.

Required fix:

- Store provider-reported input tokens, output tokens, total tokens, cost, model, and provider request id.
- Enforce limits against total token and cost budgets.

Acceptance test:

- A known provider response updates all usage fields accurately.
- Budget exceeded paths block further calls.

### 16. Worker and queue sizing are not production-tuned

Problem:

Celery worker/beat services exist, but concurrency, queue separation, retry policy, and resource limits are not fully tuned for production.

Required fix:

- Define queue names for AI runs, maintenance, notifications, and cleanup.
- Set worker concurrency and memory limits.
- Add retry/backoff policy for provider and Telegram failures.

Acceptance test:

- Load test shows stable queue latency and no uncontrolled retries.

## Observability and operations gaps

### 17. KPIs exist but alerts do not

Problem:

The dashboard returns useful operational metrics, but there is no external alerting or incident workflow.

Required fix:

- Add alerts for API down, Hermes down, high failure rate, high latency, queue backlog, low disk, DB backup failure, and budget pressure.

Acceptance test:

- A simulated failure triggers an alert within the agreed time.

### 18. Logs are not centralized

Problem:

Container logs are available locally, but there is no central log retention/search strategy.

Required fix:

- Add structured JSON logs.
- Ship logs to a VPS-local or external log system.
- Add request ids and run ids across API, Hermes, and worker logs.

Acceptance test:

- One failed user journey can be traced from frontend/API to Hermes/runtime/provider.

### 19. Backup and restore are not proven

Problem:

Database volumes exist, but backup/restore validation is not part of the release gate.

Required fix:

- Automate encrypted Postgres backups.
- Test restore into a clean staging database.
- Document RPO/RTO.

Acceptance test:

- Restore test succeeds and app can boot from restored data.

## Maintainability concerns

### 20. Large modules need boundaries before feature growth

Files:

- `app/api/admin.py`
- `app/services/agent_service.py`

Problem:

Some modules combine routing, business rules, metrics, and orchestration logic.

Risk:

Future changes become harder to test and easier to break.

Required fix:

- Move dashboard metric aggregation into a service.
- Move agent run lifecycle rules into smaller units.
- Keep API route handlers thin.

Acceptance test:

- Route tests remain passing.
- Service-level tests cover metric and run lifecycle rules.

### 21. Some tests inspect source text instead of behavior

Problem:

Source-inspection tests are useful for guardrails but cannot prove runtime behavior.

Risk:

Tests can pass while production behavior is broken.

Required fix:

- Keep source-inspection tests only for static release checks.
- Add behavioral integration tests for admin dashboard, Hermes lifecycle, Telegram, quotas, and WebSocket auth.

Acceptance test:

- Critical release requirements have runtime tests, not only text checks.

## Required pre-deploy checklist

These items should be completed before production deployment:

- Fix frontend production API URL behavior.
- Add production migration/release step.
- Validate real Hermes runtime on staging VPS.
- Fix or explicitly redesign production Hermes Docker lifecycle.
- Fix Telegram webhook live reply flow.
- Resolve frontend and desktop dependency audit findings.
- Sign desktop artifacts and validate update feed if desktop is part of launch.
- Harden WebSocket authentication and redact token-bearing logs.
- Add production secret validation.
- Add Nginx security headers.
- Add Redis-backed rate limiting.
- Define WebSocket scaling strategy.
- Validate provider token/cost accounting.
- Add backup automation and perform restore test.
- Add external monitoring and alerting.
- Run load test against staging.
- Run real end-to-end journey from public domain:
  - Admin login.
  - Create profile.
  - Add API key/budget.
  - Create employee.
  - Assign profile.
  - Chat through web.
  - Chat through Telegram.
  - Confirm run/session/cost/KPI records.
  - Restart Hermes and confirm recovery.

## Suggested work plan

### Phase 1: Production blockers

Goal: Make a staging VPS deployment actually behave like production.

Tasks:

- Fix frontend API URL.
- Add migration release step.
- Fix Hermes production lifecycle.
- Add real Hermes runtime E2E test.
- Fix Telegram live reply.
- Add strict production secret validation.

Exit criteria:

- Staging VPS public-domain journey passes without mock services.

### Phase 2: Security hardening

Goal: Reduce high-risk exposure before real users.

Tasks:

- Resolve dependency audit findings.
- Harden WebSocket token flow.
- Add Nginx security headers and CSP.
- Reduce Docker socket risk.
- Review token storage strategy.

Exit criteria:

- Dependency audits pass or have approved documented exceptions.
- Security smoke scan passes agreed baseline.

### Phase 3: Operations and observability

Goal: Make failures visible and recoverable.

Tasks:

- Add centralized structured logs.
- Add alerts for health, latency, failures, queues, backups, and budgets.
- Automate backup and restore validation.
- Add deployment runbook.

Exit criteria:

- Simulated failures create alerts.
- Restore test succeeds.

### Phase 4: Scale validation

Goal: Prove the platform can handle expected production load.

Tasks:

- Move rate limits to Redis.
- Define worker concurrency and queue separation.
- Load test API, chat, Hermes runtime, and dashboard.
- Decide WebSocket sticky sessions vs pub/sub.

Exit criteria:

- Load test meets target latency, error rate, and resource usage.

### Phase 5: Desktop release readiness

Goal: Make desktop safe to distribute.

Tasks:

- Upgrade Electron/Electron Builder dependency chain.
- Configure Windows code signing.
- Validate installer, launch, update, and rollback.

Exit criteria:

- Signed desktop release installs and updates successfully on a clean Windows VM.

## Final readiness gate

The platform can be considered production-ready only when:

- All critical blockers are closed.
- Staging VPS deployment passes the full real journey.
- Dependency audit is clean or exceptions are approved.
- Backup restore has been tested.
- Monitoring and alerts are active.
- Load test passes expected usage targets.
- Desktop release is signed and update-tested if included in launch.
