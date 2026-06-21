# Production Deployment Final

This is the final operational path for AgentSaaS deployments.

## Modes

- Current deployment mode: `llama.cpp` via OpenAI-compatible endpoint
- Final production mode: `MiniMax`

## Files to use

- Current `llama.cpp` mode:
  - copy `.env.production.llama.example` to `.env.production`
- Final `MiniMax` mode:
  - copy `.env.production.minimax.example` to `.env.production`

## Safe deploy command

```powershell
.\deploy\backup.ps1
.\deploy\production_readiness_check.ps1
docker compose --env-file .env.production -f docker-compose.production.yml up -d --build
```

## Post-deploy verification

```powershell
docker compose --env-file .env.production -f docker-compose.production.yml ps
docker logs agentsaas-api-1 --tail 100
docker logs agentsaas-hermes-orchestrator-1 --tail 100
docker logs agentsaas-hermes-runtime-1 --tail 100
.\deploy\smoke_test.ps1 -BaseUrl https://your-domain.example -AdminEmail admin@company.com -AdminPassword admin123 -Provider openai
```

For the final MiniMax deployment, switch the smoke provider argument:

```powershell
.\deploy\smoke_test.ps1 -BaseUrl https://your-domain.example -AdminEmail admin@company.com -AdminPassword admin123 -Provider minimax
```

## Data safety rules

- Use `up -d --build` for normal upgrades.
- Do not use `docker compose down -v` on production.
- Always create backups before upgrades.
- Keep backups outside the VPS as well.

## Desktop release sequence

```powershell
cd desktop
npm run release:check
npm run build:release
```

Set before release when available:

- `UPDATE_FEED_URL`
- `CSC_LINK`
- `CSC_KEY_PASSWORD`

## Current recommended rollout order

1. Deploy VPS with `.env.production.llama.example`-based config.
2. Verify admin, chat, Hermes, and desktop activation.
3. Verify backups and restore on staging.
4. Add Telegram bot and verify live webhook.
5. Switch to `.env.production.minimax.example` when MiniMax key is ready.
