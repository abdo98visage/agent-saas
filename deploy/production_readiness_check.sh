#!/usr/bin/env bash
set -euo pipefail

APP_HOME="${AGENTSAAS_HOME:-$(pwd)}"
ENV_FILE="${ENV_FILE:-$APP_HOME/.env.production}"
COMPOSE_FILE="${COMPOSE_FILE:-$APP_HOME/compose.yml}"

fail() {
  echo "Production readiness check failed: $*" >&2
  exit 1
}

[[ -f "$ENV_FILE" ]] || fail "Missing $ENV_FILE"
[[ -f "$COMPOSE_FILE" ]] || fail "Missing $COMPOSE_FILE"

env_content="$(cat "$ENV_FILE")"
compose_content="$(cat "$COMPOSE_FILE")"

for required in \
  "ENVIRONMENT=production" \
  "DEBUG=False" \
  "DOMAIN=" \
  "SECRET_KEY=" \
  "FERNET_KEY=" \
  "POSTGRES_PASSWORD=" \
  "DATABASE_URL=" \
  "REDIS_URL=" \
  "LLM_PROVIDER=minimax" \
  "MINIMAX_API_KEY=" \
  "HERMES_ORCHESTRATOR_SECRET=" \
  "HERMES_ORCHESTRATOR_URL=" \
  "NEXT_PUBLIC_API_URL=/api" \
  "AGENTSAAS_DATA_DIR="
do
  grep -Fq "$required" "$ENV_FILE" || fail "Missing required setting: $required"
done

for forbidden in \
  "replace-with" \
  "change-me-in-production" \
  "POSTGRES_PASSWORD=postgres" \
  "LLM_PROVIDER=mock" \
  "NEXT_PUBLIC_API_URL=http://localhost" \
  "MINIMAX_API_KEY=MINIMAX_API_KEY"
do
  if grep -Fq "$forbidden" "$ENV_FILE"; then
    fail "Unsafe placeholder/default value found: $forbidden"
  fi
done

echo "$env_content" | grep -Eq '^ALLOWED_ORIGINS=\["https://' || fail "ALLOWED_ORIGINS must use HTTPS"
echo "$env_content" | grep -Eq '^HERMES_ORCHESTRATOR_SECRET=.{32,}$' || fail "HERMES_ORCHESTRATOR_SECRET must be at least 32 chars"
echo "$env_content" | grep -Eq '^FERNET_KEY=.{40,}$' || fail "FERNET_KEY must be present"

echo "$compose_content" | grep -Fq "caddy:" || fail "Release compose must include Caddy"
echo "$compose_content" | grep -Fq "hermes-runtime:" || fail "Release compose must include hermes-runtime"
echo "$compose_content" | grep -Fq "HERMES_MANAGED_EXTERNALLY: \"true\"" || fail "Hermes orchestrator must use externally managed runtime"
echo "$compose_content" | grep -Fq "/opt/agentsaas/data" || fail "Release compose must default to /opt/agentsaas/data bind mounts"
if echo "$compose_content" | grep -Fq "/var/run/docker.sock"; then
  fail "Production release compose must not mount the Docker socket"
fi

docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" config >/dev/null
echo "Production readiness config check passed."
