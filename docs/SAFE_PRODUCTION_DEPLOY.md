# Safe Production Deploy

This document defines the safe deployment and upgrade flow for AgentSaaS so that:

- PostgreSQL data is preserved
- Hermes profile data is preserved
- updates do not delete user data
- rollback is possible

## Why data should persist by default

The production stack uses Docker named volumes in `docker-compose.production.yml`:

- `postgres_data`
- `redis_data`
- `hermes_profiles`

As long as you deploy with:

```powershell
docker compose --env-file .env.production -f docker-compose.production.yml up -d --build
```

the containers may be recreated, but the named volumes stay attached and the data remains.

## What will delete data

Do not run these commands on production unless you intentionally want to destroy data:

```powershell
docker compose -f docker-compose.production.yml down -v
docker volume rm <volume>
```

`down -v` removes named volumes, which means:

- PostgreSQL data can be lost
- Hermes profile files can be lost
- Redis state can be lost

## Safe upgrade procedure

### 1. Create backups first

```powershell
.\deploy\backup.ps1
```

This creates:

- SQL dump for PostgreSQL
- tar archive for Hermes profiles

### 2. Validate production config

```powershell
.\deploy\production_readiness_check.ps1
```

### 3. Pull the new code

```powershell
git pull
```

### 4. Rebuild and restart safely

```powershell
docker compose --env-file .env.production -f docker-compose.production.yml up -d --build
```

This is the safe command for normal upgrades.

### 5. Verify health

```powershell
docker compose --env-file .env.production -f docker-compose.production.yml ps
docker logs agentsaas-api-1 --tail 100
docker logs agentsaas-hermes-orchestrator-1 --tail 100
docker logs agentsaas-hermes-runtime-1 --tail 100
```

Then verify:

- admin login works
- API `/api/status` is healthy
- Hermes status is healthy
- one employee chat works

### 6. Roll back if needed

If the release is bad:

1. restore the previous code or image version
2. restore backups if the schema/data changed incorrectly

```powershell
.\deploy\restore.ps1 -DatabaseBackup .\backups\agentsaas-db-YYYYMMDD-HHMMSS.sql -HermesProfilesBackup .\backups\agentsaas-hermes-profiles-YYYYMMDD-HHMMSS.tar
```

## Extra protection recommendations

- Never deploy on production without running `.\deploy\backup.ps1` first.
- Never use `down -v` on production.
- Keep backups on storage outside the VPS as well, not only on the same disk.
- Test restore on staging, not only backup creation.
- Use a staging VPS before production upgrades.
- Tag releases so rollback to previous code is fast.

## Desktop update safety

Desktop app updates do not delete server data because:

- PostgreSQL lives on the server volume
- Hermes profiles live on the server volume
- desktop EXE is only a client

The desktop update risk is client-side only:

- broken installer
- broken auto-update feed
- activation/login regressions

That is why desktop releases should be validated on staging before broad distribution.
