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
if [[ ! "$POSTGRES_DB" =~ ^[A-Za-z_][A-Za-z0-9_]*$ ]]; then
  echo "POSTGRES_DB contains unsupported characters." >&2
  exit 1
fi
RESTORE_ID="$(date -u +%Y%m%d%H%M%S)"
TEMP_DB="${POSTGRES_DB}_restore_${RESTORE_ID}"
ROLLBACK_DB="${POSTGRES_DB}_before_${RESTORE_ID}"
SERVICES_STOPPED=false

restart_services() {
  if [[ "$SERVICES_STOPPED" == "true" ]]; then
    "${COMPOSE[@]}" up -d api worker beat hermes-orchestrator hermes-runtime || true
  fi
}
trap restart_services EXIT

"${COMPOSE[@]}" stop api worker beat hermes-orchestrator hermes-runtime
SERVICES_STOPPED=true

"${COMPOSE[@]}" exec -T db createdb -U "$POSTGRES_USER" "$TEMP_DB"
if ! gpg --batch --decrypt "$BACKUP_DIR/postgres.sql.gpg" \
  | "${COMPOSE[@]}" exec -T db psql -U "$POSTGRES_USER" -d "$TEMP_DB" -v ON_ERROR_STOP=1; then
  "${COMPOSE[@]}" exec -T db dropdb -U "$POSTGRES_USER" --if-exists "$TEMP_DB"
  echo "Restore validation database import failed; production database was not changed." >&2
  exit 1
fi

"${COMPOSE[@]}" exec -T db psql -U "$POSTGRES_USER" -d "$TEMP_DB" -v ON_ERROR_STOP=1 \
  -c "SELECT version_num FROM alembic_version LIMIT 1;" >/dev/null

profiles_stage="$APP_HOME/data/hermes/profiles.restore-$RESTORE_ID"
attachments_stage="$APP_HOME/data/attachments.restore-$RESTORE_ID"
knowledge_stage="$APP_HOME/data/knowledge.restore-$RESTORE_ID"
mkdir -p "$profiles_stage" "$attachments_stage" "$knowledge_stage"
knowledge_restored=false
gpg --batch --decrypt "$BACKUP_DIR/hermes-profiles.tar.gz.gpg" \
  | tar -C "$profiles_stage" --strip-components=1 -xzf -
gpg --batch --decrypt "$BACKUP_DIR/attachments.tar.gz.gpg" \
  | tar -C "$attachments_stage" --strip-components=1 -xzf -
if [[ -f "$BACKUP_DIR/knowledge.tar.gz.gpg" ]]; then
  gpg --batch --decrypt "$BACKUP_DIR/knowledge.tar.gz.gpg" \
    | tar -C "$knowledge_stage" --strip-components=1 -xzf -
  knowledge_restored=true
fi

"${COMPOSE[@]}" exec -T db psql -U "$POSTGRES_USER" -d postgres -v ON_ERROR_STOP=1 \
  -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname IN ('$POSTGRES_DB', '$TEMP_DB') AND pid <> pg_backend_pid();" \
  -c "ALTER DATABASE \"$POSTGRES_DB\" RENAME TO \"$ROLLBACK_DB\";" \
  -c "ALTER DATABASE \"$TEMP_DB\" RENAME TO \"$POSTGRES_DB\";"

mv "$APP_HOME/data/hermes/profiles" "$APP_HOME/data/hermes/profiles.before-$RESTORE_ID"
mv "$profiles_stage" "$APP_HOME/data/hermes/profiles"
mv "$APP_HOME/data/attachments" "$APP_HOME/data/attachments.before-$RESTORE_ID"
mv "$attachments_stage" "$APP_HOME/data/attachments"
if [[ "$knowledge_restored" == "true" ]]; then
  [[ -d "$APP_HOME/data/knowledge" ]] && mv "$APP_HOME/data/knowledge" "$APP_HOME/data/knowledge.before-$RESTORE_ID"
  mv "$knowledge_stage" "$APP_HOME/data/knowledge"
fi

"${COMPOSE[@]}" up -d
SERVICES_STOPPED=false
trap - EXIT
echo "Restore completed. Rollback database retained as: $ROLLBACK_DB"
