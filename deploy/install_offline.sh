#!/usr/bin/env bash
set -euo pipefail

BUNDLE="${1:?Usage: install_offline.sh BUNDLE_DIR COSIGN_PUBLIC_KEY}"
PUBLIC_KEY="${2:?Usage: install_offline.sh BUNDLE_DIR COSIGN_PUBLIC_KEY}"
APP_HOME="${AGENTSAAS_HOME:-/opt/agentsaas}"
command -v docker >/dev/null
command -v cosign >/dev/null
cosign verify-blob --key "$PUBLIC_KEY" --signature "$BUNDLE/release-manifest.sig" "$BUNDLE/release-manifest.json" >/dev/null
PYTHONPATH="$BUNDLE" python "$BUNDLE/scripts/verify_release_bundle.py" "$BUNDLE"

for archive in "$BUNDLE"/images/*.tar.gz; do gzip -dc "$archive" | docker load; done
mkdir -p "$APP_HOME/deploy" "$APP_HOME/releases"
cp "$BUNDLE/compose.yml" "$APP_HOME/compose.yml"
cp "$BUNDLE/deploy/Caddyfile" "$APP_HOME/deploy/Caddyfile"
cp "$BUNDLE/deploy/"*.sh "$APP_HOME/"
chmod +x "$APP_HOME/"*.sh
cp "$BUNDLE/release-manifest.json" "$APP_HOME/releases/$(basename "$BUNDLE").json"
echo "Bundle verified and images loaded. Configure $APP_HOME/.env.production, then run production_readiness_check.sh."
