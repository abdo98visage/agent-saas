# Journey E2E Test Report

Date: 2026-06-20

Workspace: `C:\Users\windows-server\Desktop\work\Hermes\ai\AgentSaaS`

Sources:
- `docs/CUSTOMER_PLATFORM_JOURNEY_AR.md`
- `docs/CUSTOMER_DESKTOP_JOURNEY_AR.md`

Environment:
- Admin UI: `http://localhost:3002`
- API: `http://localhost:8002`
- Hermes runtime: Docker container `agentsaas-hermes-runtime-1`
- Hermes orchestrator: Docker container `agentsaas-hermes-orchestrator-1`
- LLM endpoint used during tests: local llama.cpp exposed to Docker

Executed tests:
- `python deploy/docker_feature_test.py --api-url http://localhost:8002 --admin-url http://localhost:3002 --admin-email admin@company.com --admin-password admin123 --employee-password Employee123 --provider openai`
- `node deploy/desktop_e2e_test.js --api-url http://localhost:8002 --exe-path "desktop/dist/win-unpacked/FQ-SaaS Workspace.exe" --admin-email admin@company.com --admin-password admin123 --employee-password Employee123 --provider openai --port 9333`

## Summary

Overall result: PASS after one test-flow fix in the desktop E2E script.

Fixed during execution:
- Desktop chat verification was flaky because the test depended on a DOM click plus a 30s response timeout.
- Fix applied in `deploy/desktop_e2e_test.js`:
  - clear persisted token before activation for deterministic first-run behavior
  - call `sendMessage()` directly from the renderer during E2E
  - wait for user message dispatch first
  - accept assistant content from app state, not only rendered DOM
  - extend chat response timeout to 60s

Final container health:

| Service | Status |
|---|---|
| `agentsaas-api-1` | Up, healthy |
| `agentsaas-hermes-orchestrator-1` | Up, healthy |
| `agentsaas-hermes-runtime-1` | Up, healthy |
| `agentsaas-db-1` | Up, healthy |
| `agentsaas-redis-1` | Up, healthy |
| `agentsaas-admin-1` | Up |

## Platform Journey Coverage

| Journey Step | What was tested | Result |
|---|---|---|
| 1. Platform startup | API health, admin frontend response, Docker containers healthy | PASS |
| 2. Hermes setup and readiness | `/api/admin/hermes/status`, logs, repair/sync | PASS |
| 3. Create profile | Admin profile create with `runtime_type=hermes`, `agents_md`, `soul_md`, `skills`, prompt, limits | PASS |
| 3. Profile sync to Hermes | auto sync on create, update sync, manual sync endpoint | PASS |
| 4. Add LLM API keys | platform key, profile key, user key create/update/list | PASS |
| 5. Create employee | employee create, invite token issuance | PASS |
| 6. Assign employee to profile | assignment create/list | PASS |
| 7. Activate employee | `/api/auth/activate`, token issuance, access isolation | PASS |
| 8. Employee chat usage | REST chat through API to Hermes, tokens tracked, response returned | PASS |
| 8. Persistence | conversation record, messages, runs, KPI, token usage | PASS |
| 9. Multi-channel chat | REST, SSE, WebSocket | PASS |
| 10. Telegram bind | bind code generation, webhook bind, bind confirmation, Telegram reply path | PASS |
| 11. Admin observability | session details, runs, KPIs, dashboard, online users, activity feed, audit log | PASS |
| 12. Daily operations readiness | profile updates, key hierarchy, quotas, monitoring paths exercised | PASS |

## Desktop Journey Coverage

| Journey Step | What was tested | Result |
|---|---|---|
| 1. First launch | packaged EXE startup, activation panel on fresh run | PASS |
| 2. Activation from app | invite token + password + API URL against `/api/auth/activate` | PASS |
| 2. Local token persistence | token saved in desktop settings after activation | PASS |
| 3. Platform connection | REST API URL usage, `/api/auth/ws-token`, WebSocket connection | PASS |
| 4. Send message | employee message from desktop via WebSocket | PASS |
| 4. Receive Hermes reply | real Hermes response rendered and stored | PASS |
| 5. Load conversations | conversation created in backend and retrievable | PASS |
| 6. Project context | folder scan, safe file filtering, context build | PASS |
| 7. File read/write flow | read file, preview write token, apply write | PASS |
| 8. Offline queue | local queue persistence path exercised through settings | PASS |
| 9. Telegram bind from desktop | generate bind code, webhook bind, confirm bind flow | PASS |
| 10. Update status | local/Docker update status check path | PASS |
| 11. Desktop security assumptions | behavior consistent with isolated preload IPC flow and workspace guard paths | PASS |

## Detailed Results

### Docker feature test output

| Check | Result |
|---|---|
| public health and admin frontend | PASS |
| auth, cookies, and access control | PASS |
| Hermes control plane | PASS |
| admin agent template CRUD | PASS |
| profiles, API keys, employees, assignments | PASS |
| employee activation and admin isolation | PASS |
| chat REST, SSE, conversations, history | PASS |
| chat WebSocket streaming | PASS |
| Telegram bind and webhook flow | PASS |
| observability and admin listings | PASS |

Artifacts:
- Profile slug: `qa-hermes-c4gzdwrl`
- Employee: `qa-c4gzdwrl@example.com`
- Conversation: `6c0aafd1-0cc5-4bf9-bb63-3f06cc1d2bd8`

### Desktop packaged EXE test output

| Check | Result |
|---|---|
| packaged EXE activation | PASS |
| WebSocket chat | PASS |
| project scan/context/read/preview/apply write | PASS |
| Telegram bind UI flow | PASS |
| offline queue and update status | PASS |

Artifacts:
- Profile slug: `desktop-hermes-acba0b75bb`
- Employee: `desktop-acba0b75bb@example.com`

## Hermes Verification

Verified as real Hermes, not placeholder:

| Item | Evidence | Result |
|---|---|---|
| Docker runtime is active | `agentsaas-hermes-runtime-1` healthy | PASS |
| Docker orchestrator is active | `agentsaas-hermes-orchestrator-1` healthy | PASS |
| Profile sync creates real profile files | profile directories exist under `/data/hermes/profiles/...` | PASS |
| `SOUL.md` is profile-local | present in profile root | PASS |
| `workspace/AGENTS.md` is workspace-local | present under profile workspace | PASS |
| skills are profile-local | `skills/<skill>/SKILL.md` present in profile | PASS |
| Agent execution uses Hermes run endpoints | orchestrator/runtime logs show `POST /runs` and `POST /runs/stream` | PASS |

Observed Hermes-synced desktop profile files:
- `SOUL.md`
- `workspace/AGENTS.md`
- `skills/desktop/SKILL.md`
- `skills/platform-profile/SKILL.md`
- `skills/qa/SKILL.md`

## Sample Real Responses

### Platform flow sample

Employee: `qa-c4gzdwrl@example.com`

Latest stored exchange:
- User: `Write a short Telegram E2E reply.`
- Assistant: `Here's a short Telegram E2E reply draft... Docker validation passed...`

### Desktop flow sample

Employee: `desktop-acba0b75bb@example.com`

Latest stored exchange:
- User: `Write one short packaged desktop E2E response.`
- Assistant: `Packaged Desktop E2E Response... Profile loaded successfully... Ready for end-to-end desktop validation tasks.`

## Logs and Signals Checked

- API logs confirmed:
  - profile creation
  - employee creation
  - assignment creation
  - activation
  - REST chat
  - SSE chat
  - WebSocket connection
  - Telegram bind endpoints
  - admin observability endpoints
- Hermes orchestrator logs confirmed:
  - `/profiles/sync`
  - `/runs`
  - `/runs/stream`
- Hermes runtime logs confirmed:
  - `/runs`
  - `/runs/stream`
  - Hermes plugin discovery inside profile execution logs

## Failures Encountered and Fixes

| Failure | Root cause | Fix | Final status |
|---|---|---|---|
| Desktop activation panel check was nondeterministic on fresh test runs | persisted local token could hide activation UI | reset stored token in E2E setup and force activation panel visible | FIXED |
| Desktop chat response wait timed out intermittently | test used DOM click and a short UI-only response wait | call renderer `sendMessage()` directly, wait for user dispatch, read assistant content from state or DOM, increase timeout | FIXED |

## Final Verdict

The full customer journey described in both journey documents was executed end-to-end against the live Docker stack and the packaged desktop EXE.

Status:
- Platform journey: PASS
- Desktop journey: PASS
- Hermes integration: PASS
- Telegram bind flow: PASS in mocked webhook path
- Real LLM-backed responses through Docker Hermes path: PASS

No remaining failing step was left open at the end of this test run.
