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

RECIPIENT="${AGENTSAAS_BACKUP_RECIPIENT:-$(get_env AGENTSAAS_BACKUP_RECIPIENT)}"
if [[ -z "$RECIPIENT" ]]; then
  echo "AGENTSAAS_BACKUP_RECIPIENT is required; import the off-host GPG public key first." >&2
  exit 1
fi
if ! gpg --batch --list-keys "$RECIPIENT" >/dev/null 2>&1; then
  echo "The configured backup GPG public key is not imported: $RECIPIENT" >&2
  exit 1
fi

umask 077
mkdir -p "$BACKUP_DIR"
POSTGRES_USER="$(get_env POSTGRES_USER)"
POSTGRES_DB="$(get_env POSTGRES_DB)"

"${COMPOSE[@]}" exec -T db pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB" \
  | gpg --batch --yes --trust-model always --encrypt --recipient "$RECIPIENT" \
      --output "$BACKUP_DIR/postgres.sql.gpg"

tar -C "$APP_HOME/data/hermes" -czf - profiles \
  | gpg --batch --yes --trust-model always --encrypt --recipient "$RECIPIENT" \
      --output "$BACKUP_DIR/hermes-profiles.tar.gz.gpg"

tar -C "$APP_HOME/data" -czf - attachments \
  | gpg --batch --yes --trust-model always --encrypt --recipient "$RECIPIENT" \
      --output "$BACKUP_DIR/attachments.tar.gz.gpg"

tar -C "$APP_HOME/data" -czf - knowledge \
  | gpg --batch --yes --trust-model always --encrypt --recipient "$RECIPIENT" \
      --output "$BACKUP_DIR/knowledge.tar.gz.gpg"

(
  cd "$BACKUP_DIR"
  sha256sum postgres.sql.gpg hermes-profiles.tar.gz.gpg attachments.tar.gz.gpg knowledge.tar.gz.gpg > manifest.sha256
)

echo "Encrypted backup created: $BACKUP_DIR"
