# Release Checklist

Use this checklist before every production release.

## Server

- `.env.production` exists and has no placeholder secrets.
- Correct provider mode is selected:
  - `openai` + `OPENAI_BASE_URL` for current `llama.cpp`
  - `minimax` + `MINIMAX_API_KEY` for final production
- TLS files exist in `deploy/certs/`
- `.\deploy\production_readiness_check.ps1` passes
- `.\deploy\backup.ps1` completed successfully
- No destructive command such as `down -v` is planned

## Verification

- `pytest -q` passes
- Local Docker E2E journey passes
- Desktop EXE E2E journey passes
- Hermes status is healthy
- Dashboard stats load
- At least one employee chat succeeds

## Desktop

- `desktop/desktop-config.json` points to the correct API URL
- `npm run release:check` reviewed
- If public distribution is planned:
  - `UPDATE_FEED_URL` configured
  - signing certificate env vars configured
- Installer build completed successfully

## Deploy

- `docker compose --env-file .env.production -f docker-compose.production.yml up -d --build`
- Health checks pass after deploy
- Admin login works
- Employee activation works
- Employee chat works

## After deploy

- Backup artifacts retained
- Logs checked for API / Hermes errors
- Dashboard alerts reviewed
- If release is bad, rollback plan is ready
