#!/usr/bin/env bash
set -euo pipefail

APP_HOME="${AGENTSAAS_HOME:-/opt/agentsaas}"
COMPOSE=(docker compose --env-file "$APP_HOME/.env.production" -f "$APP_HOME/compose.yml")

usage() {
  cat <<'USAGE'
Usage: agentsaas <command>

Commands:
  status              Show service status
  logs [service]      Follow logs
  update              Pull images and restart services
  smoke               Run production smoke test
  backup              Create a backup
  restore <path>      Restore a backup directory
  restart             Restart the stack
USAGE
}

command="${1:-}"
shift || true

case "$command" in
  status)
    "${COMPOSE[@]}" ps
    ;;
  logs)
    "${COMPOSE[@]}" logs -f --tail=200 "$@"
    ;;
  update)
    cd "$APP_HOME"
    ./backup.sh
    ./production_readiness_check.sh
    "${COMPOSE[@]}" pull
    "${COMPOSE[@]}" up -d
    echo "Waiting for API container health..."
    deadline=$((SECONDS + 180))
    while (( SECONDS < deadline )); do
      health="$("${COMPOSE[@]}" ps api --format json 2>/dev/null | jq -r '.Health // empty' || true)"
      if [[ "$health" == "healthy" ]]; then
        break
      fi
      sleep 3
    done
    if [[ "${health:-}" != "healthy" ]]; then
      "${COMPOSE[@]}" ps
      "${COMPOSE[@]}" logs --tail=100 api
      echo "API did not become healthy within 180 seconds." >&2
      exit 1
    fi
    "${COMPOSE[@]}" exec -T api python -m scripts.bootstrap_production
    ;;
  smoke)
    cd "$APP_HOME"
    ./smoke_test.sh
    ;;
  backup)
    cd "$APP_HOME"
    ./backup.sh
    ;;
  restore)
    cd "$APP_HOME"
    ./restore.sh "${1:-}"
    ;;
  restart)
    "${COMPOSE[@]}" restart
    ;;
  -h|--help|"")
    usage
    ;;
  *)
    echo "Unknown command: $command" >&2
    usage
    exit 1
    ;;
esac
