# Journey E2E Test Report - 2026-06-21

## Scope

This report covers a full end-to-end validation of the platform on Docker and the packaged desktop EXE, using the customer journey documents as the target behavior baseline.

Runtime boundary respected during testing:

- Only the Docker Hermes runtime was tested and modified.
- The Windows host Hermes runtime was not touched.

Current test LLM path:

- Docker Hermes -> `llama.cpp` OpenAI-compatible endpoint
- Endpoint used from Docker: `http://host.docker.internal:54175/v1/chat/completions`

## Final Result

- Docker platform journey: `PASS`
- Desktop EXE journey: `PASS`
- Python regression suite: `112 passed in 2.19s`

## What Was Tested

### Docker platform journey

Verified end-to-end:

- API health and admin frontend availability
- Admin login, cookies, session handling, and access control
- Hermes control plane health, logs, and repair/sync
- Agent template CRUD
- Profile creation, update, sync, and Hermes linkage
- API key creation at profile, platform, and user levels
- Employee creation, quotas, assignment, and activation
- REST chat
- SSE chat
- WebSocket chat
- Telegram bind and webhook flow
- Admin observability endpoints, KPI, activity feed, audit log, sessions, and listings

Final Docker automated run result:

- `PASS public health and admin frontend`
- `PASS auth, cookies, and access control`
- `PASS Hermes control plane`
- `PASS admin agent template CRUD`
- `PASS profiles, API keys, employees, assignments`
- `PASS employee activation and admin isolation`
- `PASS chat REST, SSE, conversations, history`
- `PASS chat WebSocket streaming`
- `PASS Telegram bind and webhook flow`
- `PASS observability and admin listings`

Run summary:

- `SUMMARY all Docker feature checks passed`

### Desktop EXE journey

Verified end-to-end:

- Employee activation from invite token
- WebSocket connection from packaged EXE
- Chat from desktop app
- Local project scan
- Project context building
- Local file read and preview
- Apply workspace changes locally on the employee machine path
- Telegram bind UI flow
- Offline queue and update status

Final desktop automated run result:

- `PASS desktop packaged EXE activation`
- `PASS desktop WebSocket chat`
- `PASS desktop project scan/context/read/preview/apply write`
- `PASS desktop Telegram bind UI flow`
- `PASS desktop offline queue and update status`

## Issues Found And Fixed

### 1. Docker image missing Hermes runtime system dependencies

Problem:

- Hermes inside Docker failed during real execution because required system tools were missing.

Observed failures included:

- missing `curl`
- missing `xz`

Fix:

- Updated [Dockerfile](C:/Users/windows-server/Desktop/work/Hermes/ai/AgentSaaS/Dockerfile) to install:
  - `curl`
  - `xz-utils`
  - `nodejs`
  - `npm`

### 2. E2E stack was pointed to placeholder Minimax configuration

Problem:

- The Docker E2E stack used a placeholder Minimax configuration, while the requested real test path was the local OpenAI-compatible `llama.cpp` endpoint.

Fix:

- Updated [docker-compose.e2e.yml](C:/Users/windows-server/Desktop/work/Hermes/ai/AgentSaaS/docker-compose.e2e.yml) so the Docker test environment uses:
  - `LLM_PROVIDER=openai`
  - `OPENAI_BASE_URL=http://host.docker.internal:54175/v1/chat/completions`

### 3. Default model values were hardcoded to unavailable model names

Problem:

- Default templates and runtime fallbacks assumed `qwen3-14b`, which did not match the actual locally served model.

Fix:

- Added configurable `DEFAULT_MODEL` support and wired it through:
  - [app/core/config.py](C:/Users/windows-server/Desktop/work/Hermes/ai/AgentSaaS/app/core/config.py)
  - [seed_templates.py](C:/Users/windows-server/Desktop/work/Hermes/ai/AgentSaaS/seed_templates.py)
  - [app/local_hermes_runtime_app.py](C:/Users/windows-server/Desktop/work/Hermes/ai/AgentSaaS/app/local_hermes_runtime_app.py)
  - [app/services/agent_service.py](C:/Users/windows-server/Desktop/work/Hermes/ai/AgentSaaS/app/services/agent_service.py)
  - [app/schemas/admin.py](C:/Users/windows-server/Desktop/work/Hermes/ai/AgentSaaS/app/schemas/admin.py)

### 4. Hermes WebSocket chat incorrectly entered cowork mode for normal platform chat

Problem:

- Any Hermes profile on the WebSocket path could trigger cowork behavior, even for regular conversational chat without workspace context.
- This caused `apply_request` responses during plain platform chat, which is incorrect for manager/admin conversational use.

Fix:

- Updated [app/api/websocket_chat.py](C:/Users/windows-server/Desktop/work/Hermes/ai/AgentSaaS/app/api/websocket_chat.py) so cowork mode is only used when actual workspace context exists.
- Normal platform chat with Hermes profiles now remains conversational.
- Desktop cowork behavior remains available when workspace data is present.

### 5. Local reasoning model needed more realistic E2E timeout margins

Problem:

- `llama.cpp` local reasoning responses through Hermes were functionally correct but slower than the previous client timeout used in the Docker test script.

Fix:

- Increased Hermes request timeout in:
  - [app/core/config.py](C:/Users/windows-server/Desktop/work/Hermes/ai/AgentSaaS/app/core/config.py)
- Added configurable request timeout support in:
  - [deploy/docker_feature_test.py](C:/Users/windows-server/Desktop/work/Hermes/ai/AgentSaaS/deploy/docker_feature_test.py)

### 6. E2E scripts needed to force the actual model used in the test environment

Problem:

- Docker and desktop E2E scripts were not explicitly enforcing the locally available model during setup.

Fix:

- Updated:
  - [deploy/docker_feature_test.py](C:/Users/windows-server/Desktop/work/Hermes/ai/AgentSaaS/deploy/docker_feature_test.py)
  - [deploy/desktop_e2e_test.js](C:/Users/windows-server/Desktop/work/Hermes/ai/AgentSaaS/deploy/desktop_e2e_test.js)

## Verification Notes

Important runtime validation achieved:

- Hermes runtime inside Docker executed real requests successfully.
- Hermes profile sync was exercised through admin profile operations.
- REST, SSE, and WebSocket chat paths all completed successfully against the Docker Hermes runtime.
- Desktop local workspace change flow applied changes locally on the desktop test workspace path.

## Performance Notes

Observed during local `llama.cpp` testing:

- REST chat latency was around `~29s` to `~37s`
- WebSocket chat latency was around `~27s`

Interpretation:

- This is acceptable for local functional testing.
- This is slower than expected production behavior with a hosted provider such as Minimax.
- Production UX should prefer streaming/WebSocket-first behavior.

## Production Readiness Status

Current status after fixes:

- Functional end-to-end integration: ready
- Real Hermes runtime integration: ready
- Desktop local workspace cowork flow: ready
- Docker validation path: ready

Still worth monitoring for production:

- Hosted provider latency and timeout tuning
- VPS deployment hardening
- observability retention and alerting policies
- backup and persistence strategy for database and Hermes profile data

## Commands Used For Final Validation

Docker platform E2E:

```powershell
python deploy/docker_feature_test.py --api-url http://localhost:8002 --admin-url http://localhost:3002 --admin-email admin@company.com --admin-password admin123 --employee-password Employee123 --provider openai --model Qwen3.6-27B-IQ4_XS.gguf --request-timeout 120
```

Desktop EXE E2E:

```powershell
node deploy/desktop_e2e_test.js --api-url http://localhost:8002 --exe-path "desktop/dist/win-unpacked/FQ-SaaS Workspace.exe" --admin-email admin@company.com --admin-password admin123 --employee-password Employee123 --provider openai --model Qwen3.6-27B-IQ4_XS.gguf --port 9333
```

Regression suite:

```powershell
pytest -q
```

## Final Conclusion

The platform and desktop application were both tested end-to-end successfully.

The Docker path now uses a real Hermes runtime and a real local OpenAI-compatible model backend for testing. The desktop app successfully performs the intended local-workspace cowork flow. The main issues found during testing were integration and environment hardening issues, and they were fixed during the test cycle.
