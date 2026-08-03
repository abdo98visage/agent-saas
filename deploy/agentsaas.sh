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
  update <bundle> <public-key>  Verify and install an immutable offline release
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
    [[ -n "${1:-}" && -n "${2:-}" ]] || { echo "Usage: agentsaas update BUNDLE_DIR COSIGN_PUBLIC_KEY" >&2; exit 1; }
    ./upgrade.sh "$1" "$2"
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
