#!/usr/bin/env bash
set -euo pipefail

APP_HOME="${AGENTSAAS_HOME:-/opt/agentsaas}"
RELEASE_BASE_URL="${AGENTSAAS_RELEASE_BASE_URL:-https://downloads.example.com/agentsaas}"
VERSION="latest"
DOMAIN=""
ADMIN_EMAIL=""
ADMIN_PASSWORD=""
MINIMAX_KEY=""
TELEGRAM_BOT_TOKEN=""
SENTRY_DSN=""
SMTP_HOST=""
SMTP_USERNAME=""
SMTP_PASSWORD=""
API_IMAGE="${AGENTSAAS_API_IMAGE:-}"
ADMIN_IMAGE="${AGENTSAAS_ADMIN_IMAGE:-}"
HERMES_RUNTIME_IMAGE="${AGENTSAAS_HERMES_RUNTIME_IMAGE:-}"

usage() {
  cat <<'USAGE'
Usage:
  install.sh --domain app.example.com --admin-email admin@example.com --minimax-key KEY [options]

Options:
  --version VERSION
  --admin-password PASSWORD
  --telegram-bot-token TOKEN
  --sentry-dsn DSN
  --smtp-host HOST
  --smtp-username USER
  --smtp-password PASSWORD
  --api-image IMAGE
  --admin-image IMAGE
  --hermes-runtime-image IMAGE
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --domain) DOMAIN="${2:-}"; shift 2 ;;
    --admin-email) ADMIN_EMAIL="${2:-}"; shift 2 ;;
    --admin-password) ADMIN_PASSWORD="${2:-}"; shift 2 ;;
    --minimax-key) MINIMAX_KEY="${2:-}"; shift 2 ;;
    --version) VERSION="${2:-latest}"; shift 2 ;;
    --telegram-bot-token) TELEGRAM_BOT_TOKEN="${2:-}"; shift 2 ;;
    --sentry-dsn) SENTRY_DSN="${2:-}"; shift 2 ;;
    --smtp-host) SMTP_HOST="${2:-}"; shift 2 ;;
    --smtp-username) SMTP_USERNAME="${2:-}"; shift 2 ;;
    --smtp-password) SMTP_PASSWORD="${2:-}"; shift 2 ;;
    --api-image) API_IMAGE="${2:-}"; shift 2 ;;
    --admin-image) ADMIN_IMAGE="${2:-}"; shift 2 ;;
    --hermes-runtime-image) HERMES_RUNTIME_IMAGE="${2:-}"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown option: $1" >&2; usage; exit 1 ;;
  esac
done

if [[ -z "$DOMAIN" || -z "$ADMIN_EMAIL" || -z "$MINIMAX_KEY" ]]; then
  echo "Missing required --domain, --admin-email, or --minimax-key." >&2
  usage
  exit 1
fi

if [[ "$(id -u)" -ne 0 ]]; then
  echo "Run this installer with sudo or as root." >&2
  exit 1
fi

random_hex() {
  openssl rand -hex 32
}

random_fernet() {
  openssl rand -base64 32 | tr '+/' '-_'
}

install_host_dependencies() {
  if command -v apt-get >/dev/null 2>&1; then
    apt-get update
    apt-get install -y ca-certificates curl gnupg openssl jq
  elif command -v dnf >/dev/null 2>&1; then
    dnf install -y ca-certificates curl gnupg openssl jq
  elif command -v yum >/dev/null 2>&1; then
    yum install -y ca-certificates curl gnupg openssl jq
  else
    echo "Unsupported Linux distribution: missing apt-get, dnf, and yum." >&2
    exit 1
  fi

  if ! command -v docker >/dev/null 2>&1; then
    curl -fsSL https://get.docker.com | sh
  fi

  systemctl enable docker >/dev/null 2>&1 || true
  systemctl start docker >/dev/null 2>&1 || true

  if ! docker compose version >/dev/null 2>&1; then
    echo "Docker Compose plugin is not available after Docker installation." >&2
    exit 1
  fi
}

download_asset() {
  local remote_path="$1"
  local target_path="$2"
  mkdir -p "$(dirname "$target_path")"
  curl -fsSL "$RELEASE_BASE_URL/$VERSION/$remote_path" -o "$target_path"
}

prepare_files() {
  mkdir -p "$APP_HOME/deploy" "$APP_HOME/data/postgres" "$APP_HOME/data/redis" "$APP_HOME/data/hermes/profiles" "$APP_HOME/backups"

  download_asset "docker-compose.release.yml" "$APP_HOME/compose.yml"
  download_asset "deploy/Caddyfile" "$APP_HOME/deploy/Caddyfile"
  download_asset "deploy/agentsaas.sh" "$APP_HOME/agentsaas.sh"
  download_asset "deploy/production_readiness_check.sh" "$APP_HOME/production_readiness_check.sh"
  download_asset "deploy/smoke_test.sh" "$APP_HOME/smoke_test.sh"
  download_asset "deploy/backup.sh" "$APP_HOME/backup.sh"
  download_asset "deploy/restore.sh" "$APP_HOME/restore.sh"

  chmod +x "$APP_HOME"/*.sh
  ln -sf "$APP_HOME/agentsaas.sh" /usr/local/bin/agentsaas
}

write_env() {
  local env_file="$APP_HOME/.env.production"
  if [[ -f "$env_file" ]]; then
    echo "Keeping existing $env_file. Existing secrets were not rotated."
    return
  fi

  if [[ -z "$ADMIN_PASSWORD" ]]; then
    ADMIN_PASSWORD="$(openssl rand -base64 24 | tr -d '\n')"
  fi

  local secret_key fernet_key postgres_password hermes_secret
  secret_key="$(random_hex)"
  fernet_key="$(random_fernet)"
  postgres_password="$(random_hex)"
  hermes_secret="$(random_hex)"
  API_IMAGE="${API_IMAGE:-ghcr.io/example/agentsaas-api:$VERSION}"
  ADMIN_IMAGE="${ADMIN_IMAGE:-ghcr.io/example/agentsaas-admin:$VERSION}"
  HERMES_RUNTIME_IMAGE="${HERMES_RUNTIME_IMAGE:-ghcr.io/example/agentsaas-hermes-runtime:$VERSION}"

  cat > "$env_file" <<EOF
APP_NAME=FQ-SaaS
DEBUG=False
ENVIRONMENT=production
DOMAIN=$DOMAIN
ALLOWED_ORIGINS=["https://$DOMAIN"]
NEXT_PUBLIC_API_URL=/api

SECRET_KEY=$secret_key
FERNET_KEY=$fernet_key
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=480

ADMIN_EMAIL=$ADMIN_EMAIL
ADMIN_PASSWORD=$ADMIN_PASSWORD

POSTGRES_USER=agentsaas
POSTGRES_PASSWORD=$postgres_password
POSTGRES_DB=agentsaas
DATABASE_URL=postgresql+asyncpg://agentsaas:$postgres_password@db:5432/agentsaas

REDIS_URL=redis://redis:6379/0
CELERY_BROKER_URL=redis://redis:6379/1
RATE_LIMIT_BACKEND=redis
RATE_LIMIT_PER_MINUTE=100
AUTH_RATE_LIMIT_PER_MINUTE=10
WEBSOCKET_MAX_MESSAGE_BYTES=32768
KPI_TOKEN_ALERT_THRESHOLD=40000
KPI_COST_ALERT_THRESHOLD=25

LLM_PROVIDER=minimax
DEFAULT_MODEL=MiniMax-M3
MINIMAX_API_KEY=$MINIMAX_KEY
MINIMAX_BASE_URL=https://api.minimax.io/v1/chat/completions
OPENAI_API_KEY=
OPENAI_BASE_URL=
OLLAMA_BASE_URL=http://ollama:11434

HERMES_ORCHESTRATOR_URL=http://hermes-orchestrator:8788
HERMES_ORCHESTRATOR_SECRET=$hermes_secret
HERMES_ORCHESTRATOR_REQUIRE_SECRET=true
HERMES_PORT=8787
HERMES_INTERNAL_URL=http://hermes-runtime:8787
HERMES_RUN_PATH=/runs
HERMES_RUN_STREAM_PATH=/runs/stream
HERMES_HEALTH_PATH=/health
HERMES_MANAGED_EXTERNALLY=true

TELEGRAM_BOT_TOKEN=$TELEGRAM_BOT_TOKEN
TELEGRAM_WEBHOOK_SECRET=
TELEGRAM_WEBHOOK_URL=https://$DOMAIN/api/telegram/webhook

SENTRY_DSN=$SENTRY_DSN
SENTRY_ENVIRONMENT=production
SENTRY_TRACES_SAMPLE_RATE=0.1

SMTP_HOST=$SMTP_HOST
SMTP_PORT=587
SMTP_USERNAME=$SMTP_USERNAME
SMTP_PASSWORD=$SMTP_PASSWORD
SMTP_FROM_EMAIL=alerts@$DOMAIN
ALERT_NOTIFICATION_EMAILS=
ALERT_NOTIFICATION_COOLDOWN_MINUTES=60

AGENTSAAS_DATA_DIR=$APP_HOME/data
AGENTSAAS_API_IMAGE=$API_IMAGE
AGENTSAAS_ADMIN_IMAGE=$ADMIN_IMAGE
AGENTSAAS_HERMES_RUNTIME_IMAGE=$HERMES_RUNTIME_IMAGE
EOF
}

run_stack() {
  cd "$APP_HOME"
  ./production_readiness_check.sh
  docker compose --env-file .env.production -f compose.yml pull
  docker compose --env-file .env.production -f compose.yml up -d
  wait_for_api_health
  docker compose --env-file .env.production -f compose.yml exec -T api python -m scripts.bootstrap_production
}

wait_for_api_health() {
  echo "Waiting for API container health..."
  local deadline
  deadline=$((SECONDS + 180))
  while (( SECONDS < deadline )); do
    local health
    health="$(docker compose --env-file .env.production -f compose.yml ps api --format json 2>/dev/null | jq -r '.Health // empty' || true)"
    if [[ "$health" == "healthy" ]]; then
      return 0
    fi
    sleep 3
  done

  docker compose --env-file .env.production -f compose.yml ps
  docker compose --env-file .env.production -f compose.yml logs --tail=100 api
  echo "API did not become healthy within 180 seconds." >&2
  return 1
}

install_host_dependencies
prepare_files
write_env
run_stack

echo
echo "AgentSaaS deployment finished."
echo "URL: https://$DOMAIN"
echo "Admin email: $ADMIN_EMAIL"
if [[ -n "$ADMIN_PASSWORD" ]]; then
  echo "Admin password: $ADMIN_PASSWORD"
fi
echo
echo "Run: agentsaas status"
