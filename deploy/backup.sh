#!/usr/bin/env bash
set -euo pipefail

APP_HOME="${AGENTSAAS_HOME:-/opt/agentsaas}"
ENV_FILE="$APP_HOME/.env.production"
COMPOSE=(docker compose --env-file "$ENV_FILE" -f "$APP_HOME/compose.yml")
TIMESTAMP="$(date -u +%Y%m%d-%H%M%S)"
BACKUP_DIR="$APP_HOME/backups/agentsaas-$TIMESTAMP"

get_env() {
  grep -E "^$1=" "$ENV_FILE" | tail -n 1 | cut -d= -f2-
}

mkdir -p "$BACKUP_DIR"

POSTGRES_USER="$(get_env POSTGRES_USER)"
POSTGRES_DB="$(get_env POSTGRES_DB)"

"${COMPOSE[@]}" exec -T db pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB" > "$BACKUP_DIR/postgres.sql"
tar -C "$APP_HOME/data/hermes" -czf "$BACKUP_DIR/hermes-profiles.tar.gz" profiles
cp "$ENV_FILE" "$BACKUP_DIR/env.production.backup"

(
  cd "$BACKUP_DIR"
  sha256sum postgres.sql hermes-profiles.tar.gz env.production.backup > manifest.sha256
)

echo "Backup created: $BACKUP_DIR"
