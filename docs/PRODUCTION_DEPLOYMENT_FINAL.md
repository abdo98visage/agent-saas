# Production Deployment Final

This document defines the final production deployment target for AgentSaaS.

The goal is a clean VPS deployment that works from an empty Linux machine with
one command over SSH. The VPS must not require preinstalled Python, Node.js,
Hermes Agent, Docker, certificates, or manual application configuration.

## Final Target

- Platform deployment: one command on a fresh Linux VPS.
- Runtime provider: MiniMax in production.
- Agent runtime: platform-owned Hermes runtime inside Docker.
- Public access: HTTPS with automatic certificate management.
- Admin operation: controlled from the web platform after bootstrap.
- Employee app: one generic desktop app that can connect to any deployed
  platform through activation, without rebuilding per customer.

## One-Command VPS Install

The final production install should look like this:

```bash
curl -fsSL https://downloads.example.com/agentsaas/install.sh | sudo bash -s -- \
  --domain app.example.com \
  --admin-email admin@example.com \
  --minimax-key "MINIMAX_API_KEY"
```

Optional flags:

```bash
  --version v1.0.0
  --admin-password "strong-password"
  --telegram-bot-token "token"
  --sentry-dsn "dsn"
  --smtp-host "smtp.example.com"
  --smtp-username "user"
  --smtp-password "password"
```

If `--admin-password` is not provided, the installer must generate one strong
temporary password and print it once at the end of the install.

## What The Installer Must Do

`deploy/install.sh` is the only required entry point for a fresh VPS.

It must:

1. Detect supported Linux distribution.
2. Install system dependencies:
   - `curl`
   - `ca-certificates`
   - `openssl`
   - Docker Engine
   - Docker Compose plugin
3. Create `/opt/agentsaas`.
4. Download or update the production deployment bundle.
5. Generate `/opt/agentsaas/.env.production` from provided flags and generated
   secrets.
6. Start the production stack.
7. Run database migrations.
8. Seed the platform safely:
   - admin user
   - default templates
   - default skills
   - encrypted platform-level MiniMax API key
9. Run a smoke test against `https://<domain>`.
10. Print the final admin URL and credentials summary.

The installer must be idempotent. Re-running it should update the deployment
without deleting Postgres, Redis, or Hermes profile volumes.

## Production Runtime Shape

Use Docker for all application runtime dependencies.

The VPS should not need Python, Node.js, npm, or Hermes Agent installed on the
host.

Production services:

- `caddy` or `traefik`
  - public HTTP/HTTPS entrypoint
  - automatic Let's Encrypt certificates
  - reverse proxy for the platform
- `api`
  - FastAPI backend
  - runs migrations before serving
- `admin`
  - Next.js admin platform
- `worker`
  - Celery worker
- `beat`
  - Celery scheduler
- `db`
  - Postgres
- `redis`
  - Redis
- `hermes-orchestrator`
  - private control plane for Hermes profiles and runs
- `hermes-runtime`
  - private runtime service that contains the Hermes CLI

The production stack must not mount `/var/run/docker.sock` by default.

## Platform-Owned Data Layout

For production, persistent data should live under the deployment directory, not
inside a random Linux user's home directory and not inside the application source
tree.

Recommended VPS layout:

```text
/opt/agentsaas/
  compose.yml
  .env.production
  data/
    postgres/
    redis/
    hermes/
      profiles/
  backups/
```

The application code should remain immutable inside Docker images. Hermes agent
profiles and runtime state should be platform-owned persistent data.

Recommended Hermes mount:

```yaml
hermes-orchestrator:
  volumes:
    - /opt/agentsaas/data/hermes/profiles:/data/hermes/profiles

hermes-runtime:
  volumes:
    - /opt/agentsaas/data/hermes/profiles:/data/hermes/profiles:ro
```

This keeps Hermes editable through the FastAPI/admin platform while making
backup, restore, and emergency inspection straightforward. The VPS operator
does not need to edit Hermes files manually, but the data is still in a clear
deployment-owned path if recovery is needed.

Postgres and Redis may use Docker named volumes or explicit bind mounts under
`/opt/agentsaas/data`. For the simplest backup/restore story, the release
deployment should prefer explicit bind mounts under `/opt/agentsaas/data`.

## Images

The final production deployment should use prebuilt images, not build source on
the VPS.

Recommended image split:

```text
ghcr.io/<org>/agentsaas-api:<version>
ghcr.io/<org>/agentsaas-admin:<version>
ghcr.io/<org>/agentsaas-hermes-runtime:<version>
```

This keeps the VPS install fast and avoids requiring local build tooling.

Local `docker compose build` remains useful for development and staging, but the
one-command production path should pull released images.

## Environment Generation

The installer generates `.env.production`.

Required generated values:

- `SECRET_KEY`
- `FERNET_KEY`
- `POSTGRES_PASSWORD`
- `HERMES_ORCHESTRATOR_SECRET`

Required user-provided values:

- `DOMAIN`
- `ADMIN_EMAIL`
- `MINIMAX_API_KEY`

Required production values:

```env
ENVIRONMENT=production
DEBUG=False
LLM_PROVIDER=minimax
MINIMAX_BASE_URL=https://api.minimax.io/v1/chat/completions
DEFAULT_MODEL=MiniMax-M3
NEXT_PUBLIC_API_URL=/api
ALLOWED_ORIGINS=["https://app.example.com"]
TELEGRAM_WEBHOOK_URL=https://app.example.com/api/telegram/webhook
HERMES_ORCHESTRATOR_URL=http://hermes-orchestrator:8788
HERMES_INTERNAL_URL=http://hermes-runtime:8787
HERMES_ORCHESTRATOR_REQUIRE_SECRET=true
HERMES_MANAGED_EXTERNALLY=true
```

The platform should store the MiniMax key as an encrypted platform-level API key
in the database after bootstrap, so Hermes profiles can use the existing
employee/profile/platform API-key resolution flow.

## HTTPS

The final one-command deployment should not require manual certificate files.

Use Caddy or Traefik for automatic HTTPS:

- port `80` for ACME HTTP challenge and redirect
- port `443` for HTTPS
- `/api/*` proxied to `api:8000`
- `/api/chat/ws/*` proxied with WebSocket support to `api:8000`
- all other paths proxied to `admin:3000`

The current `deploy/nginx.conf` path can remain available as an advanced/manual
option, but it should not be the default one-command path because it requires
certificates to already exist.

## Post-Deploy Verification

The final Linux smoke command should be:

```bash
agentsaas smoke
```

It should validate:

- `/api/status`
- `/api/ready`
- admin login
- MiniMax provider pricing setup
- Hermes runtime status
- Hermes profile creation and sync
- platform MiniMax key resolution
- employee creation
- assignment
- employee activation
- chat through Hermes
- WebSocket token creation
- session/run observability
- KPI and usage reporting
- alert evaluation

PowerShell smoke scripts can remain for Windows development, but production must
have Bash equivalents.

## Server Operations

The installer should create a small CLI wrapper on the VPS:

```bash
agentsaas status
agentsaas logs
agentsaas update
agentsaas smoke
agentsaas backup
agentsaas restore <backup-path>
agentsaas restart
```

These commands should wrap Docker Compose and keep operators away from long
manual compose commands.

## Data Safety Rules

- Never run `docker compose down -v` in production.
- Use persistent storage for Postgres, Redis, and Hermes profiles.
- Prefer explicit bind mounts under `/opt/agentsaas/data` for simple
  backup/restore.
- Always back up before upgrades.
- Keep backups outside the VPS as well.
- Installer updates must preserve existing `.env.production` unless explicitly
  asked to rotate secrets.
- `FERNET_KEY` must never be regenerated on an existing install because it is
  required to decrypt stored provider API keys.

## Desktop App Final Direction

The production desktop app should be generic.

It should not require rebuilding per customer or per VPS domain.

Final behavior:

1. Admin deploys the platform.
2. Admin creates an employee in the web platform.
3. The platform shows a desktop activation link for that employee.
4. Employee installs the generic desktop app.
5. Employee opens the activation link.
6. The desktop app stores:
   - server URL
   - activation token or resulting auth token
7. The desktop app connects to that platform.

Recommended activation link:

```text
fqsaas://activate?server=https://app.example.com&token=<invite-token>
```

Recommended platform UI addition:

- Add a download/activation section on the employee details page.
- Show:
  - desktop download button
  - copy activation link button
  - invite token status

The current static `desktop/desktop-config.json` API URL should remain usable
for development, but production should prefer first-run activation or protocol
link configuration.

## Minimal Implementation Plan

The implementation should be staged to reduce risk.

### Phase 1: Documentation And Linux Scripts

No application behavior changes.

- Add `deploy/install.sh`.
- Add Bash equivalents for:
  - readiness check
  - smoke test
  - backup
  - restore
- Keep existing PowerShell scripts untouched.
- Add tests that verify Linux deployment assets exist.

### Phase 2: Production Compose For Released Images

Minimal compose changes.

- Add a new compose file, for example:
  - `docker-compose.release.yml`
- Keep current `docker-compose.production.yml` for source-build deployments.
- Use released images in `docker-compose.release.yml`.
- Replace default nginx path with Caddy or Traefik for automatic HTTPS.
- Preserve the current private Hermes topology.

### Phase 3: Safe Bootstrap Seed

Small backend/script change.

- Add a production-safe bootstrap command or script.
- Read admin email/password from env.
- Generate password only when missing.
- Seed templates and skills idempotently.
- Store the MiniMax key as encrypted platform-level API key.
- Do not hardcode `admin123` for production.
- Do not change existing development seed behavior unless necessary.

### Phase 4: CI Release Images

No product behavior change.

- Build and publish:
  - API image
  - admin image
  - Hermes runtime image
- Verify `hermes --version` inside the Hermes runtime image.
- Run migrations and smoke tests against the release compose file.

### Phase 5: Desktop Generic Activation

Small desktop and frontend/API change.

- Keep current `desktop-config.json` fallback.
- Add support for storing server URL after activation.
- Add custom protocol handling:
  - `fqsaas://activate?...`
- Add employee UI action to copy activation link.
- Add tests for activation parsing and server URL persistence.

### Phase 6: Final VPS Dress Rehearsal

Use a fresh VPS or clean VM.

Validate from zero:

```bash
curl -fsSL https://downloads.example.com/agentsaas/install.sh | sudo bash -s -- \
  --domain app.example.com \
  --admin-email admin@example.com \
  --minimax-key "MINIMAX_API_KEY"
```

Pass criteria:

- Docker installed by script.
- HTTPS active.
- Admin can log in.
- Hermes runtime healthy.
- New Hermes profile syncs.
- Employee can activate.
- Employee can chat through Hermes using MiniMax.
- Desktop can activate against the deployed server.
- Backup and restore verified on staging.

## Current Status

The current repository already has the main runtime shape:

- FastAPI backend
- Next.js admin app
- Postgres
- Redis
- Celery worker and beat
- Hermes orchestrator
- Hermes runtime service
- admin UI for profiles, employees, API keys, usage, and Hermes status
- Electron desktop app

The remaining work is mostly deployment packaging and bootstrap automation, not a
large product rewrite.
