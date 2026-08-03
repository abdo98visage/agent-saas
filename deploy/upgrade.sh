#!/usr/bin/env bash
set -euo pipefail

BUNDLE="${1:?Usage: upgrade.sh BUNDLE_DIR COSIGN_PUBLIC_KEY}"
PUBLIC_KEY="${2:?Usage: upgrade.sh BUNDLE_DIR COSIGN_PUBLIC_KEY}"
APP_HOME="${AGENTSAAS_HOME:-/opt/agentsaas}"
ENV_FILE="$APP_HOME/.env.production"
COMPOSE_FILE="$APP_HOME/compose.yml"
MANIFEST="$BUNDLE/release-manifest.json"
STATE_DIR="$APP_HOME/releases"
mkdir -p "$STATE_DIR"

command -v jq >/dev/null
command -v cosign >/dev/null
cosign verify-blob --key "$PUBLIC_KEY" --signature "$BUNDLE/release-manifest.sig" "$MANIFEST" >/dev/null
PYTHONPATH="$BUNDLE" python "$BUNDLE/scripts/verify_release_bundle.py" "$BUNDLE"
version="$(jq -r .version "$MANIFEST")"
[[ "$(cat "$STATE_DIR/current-version" 2>/dev/null || true)" == "$version" ]] && { echo "Release $version is already installed."; exit 0; }

for archive in "$BUNDLE"/images/*.tar.gz; do gzip -dc "$archive" | docker load; done
api_image="$(jq -r .images.api "$MANIFEST")"
admin_image="$(jq -r .images.admin "$MANIFEST")"
runtime_image="$(jq -r .images.hermes_runtime "$MANIFEST")"
caddy_image="$(jq -r .images.caddy "$MANIFEST")"
postgres_image="$(jq -r .images.postgres "$MANIFEST")"
redis_image="$(jq -r .images.redis "$MANIFEST")"
current_schema="$(docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" exec -T db sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Atc "select version_num from alembic_version"')"
if ! jq -e --arg current "$current_schema" '.compatibility.schema_compatible_from | index($current) != null' "$MANIFEST" >/dev/null; then
  echo "Release $version does not declare upgrade compatibility from schema $current_schema." >&2
  exit 1
fi

backup_output="$($APP_HOME/backup.sh)"
echo "$backup_output"
previous_env="$STATE_DIR/env-before-$version"
previous_compose="$STATE_DIR/compose-before-$version.yml"
previous_caddy="$STATE_DIR/Caddyfile-before-$version"
cp "$ENV_FILE" "$previous_env"
cp "$COMPOSE_FILE" "$previous_compose"
[[ -f "$APP_HOME/deploy/Caddyfile" ]] && cp "$APP_HOME/deploy/Caddyfile" "$previous_caddy"
replace_env() {
  local key="$1" value="$2" temp
  temp="$(mktemp)"
  awk -v key="$key" -v value="$value" 'BEGIN{done=0} $0 ~ "^" key "=" {print key "=" value; done=1; next} {print} END{if(!done) print key "=" value}' "$ENV_FILE" > "$temp"
  chmod 600 "$temp"; mv "$temp" "$ENV_FILE"
}
replace_env AGENTSAAS_API_IMAGE "$api_image"
replace_env AGENTSAAS_ADMIN_IMAGE "$admin_image"
replace_env AGENTSAAS_HERMES_RUNTIME_IMAGE "$runtime_image"
replace_env AGENTSAAS_CADDY_IMAGE "$caddy_image"
replace_env AGENTSAAS_POSTGRES_IMAGE "$postgres_image"
replace_env AGENTSAAS_REDIS_IMAGE "$redis_image"
cp "$BUNDLE/compose.yml" "$COMPOSE_FILE"
cp "$BUNDLE/deploy/Caddyfile" "$APP_HOME/deploy/Caddyfile"

rollback() {
  echo "Upgrade failed. Evaluating automatic rollback..." >&2
  cp "$previous_env" "$ENV_FILE"
  cp "$previous_compose" "$COMPOSE_FILE"
  [[ -f "$previous_caddy" ]] && cp "$previous_caddy" "$APP_HOME/deploy/Caddyfile"
  if [[ "$(jq -r .compatibility.rollback_schema_compatible "$MANIFEST")" == "true" ]]; then
    docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" up -d --pull never || true
    echo "Previous immutable images restored. The pre-upgrade encrypted backup remains available." >&2
  else
    echo "Schema is not rollback-compatible; previous data is preserved and a forward-fix or verified restore is required." >&2
  fi
}
trap rollback ERR

$APP_HOME/production_readiness_check.sh
docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" run --rm migrate
docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" up -d --pull never
deadline=$((SECONDS + 180)); health=""
while (( SECONDS < deadline )); do
  health="$(docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" ps api --format json 2>/dev/null | jq -r '.Health // empty' || true)"
  [[ "$health" == "healthy" ]] && break
  sleep 3
done
[[ "$health" == "healthy" ]]
$APP_HOME/smoke_test.sh
cp "$MANIFEST" "$STATE_DIR/$version.json"
echo "$version" > "$STATE_DIR/current-version"
trap - ERR
echo "Upgrade to $version completed and postflight smoke passed."
