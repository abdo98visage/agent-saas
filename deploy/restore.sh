#!/usr/bin/env bash
set -euo pipefail

APP_HOME="${AGENTSAAS_HOME:-/opt/agentsaas}"
ENV_FILE="$APP_HOME/.env.production"
COMPOSE=(docker compose --env-file "$ENV_FILE" -f "$APP_HOME/compose.yml")
BACKUP_DIR="${1:-}"

if [[ -z "$BACKUP_DIR" || ! -d "$BACKUP_DIR" ]]; then
  echo "Usage: restore.sh /opt/agentsaas/backups/agentsaas-YYYYMMDD-HHMMSS" >&2
  exit 1
fi

get_env() {
  grep -E "^$1=" "$ENV_FILE" | tail -n 1 | cut -d= -f2-
}

(
  cd "$BACKUP_DIR"
  sha256sum -c manifest.sha256
)

POSTGRES_USER="$(get_env POSTGRES_USER)"
POSTGRES_DB="$(get_env POSTGRES_DB)"

"${COMPOSE[@]}" stop api worker beat hermes-orchestrator hermes-runtime
"${COMPOSE[@]}" exec -T db psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"
"${COMPOSE[@]}" exec -T db psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" < "$BACKUP_DIR/postgres.sql"

rm -rf "$APP_HOME/data/hermes/profiles"
mkdir -p "$APP_HOME/data/hermes"
tar -C "$APP_HOME/data/hermes" -xzf "$BACKUP_DIR/hermes-profiles.tar.gz"

"${COMPOSE[@]}" up -d
echo "Restore completed from: $BACKUP_DIR"
