#!/usr/bin/env bash
set -euo pipefail

VERSION="${1:?Usage: build_offline_bundle.sh VERSION OUTPUT_DIR COSIGN_KEY}"
OUTPUT_DIR="${2:?Usage: build_offline_bundle.sh VERSION OUTPUT_DIR COSIGN_KEY}"
COSIGN_KEY="${3:?Usage: build_offline_bundle.sh VERSION OUTPUT_DIR COSIGN_KEY}"
: "${AGENTSAAS_API_IMAGE:?Set digest-pinned AGENTSAAS_API_IMAGE}"
: "${AGENTSAAS_ADMIN_IMAGE:?Set digest-pinned AGENTSAAS_ADMIN_IMAGE}"
: "${AGENTSAAS_HERMES_RUNTIME_IMAGE:?Set digest-pinned AGENTSAAS_HERMES_RUNTIME_IMAGE}"
: "${AGENTSAAS_CADDY_IMAGE:?Set digest-pinned AGENTSAAS_CADDY_IMAGE}"
: "${AGENTSAAS_POSTGRES_IMAGE:?Set digest-pinned AGENTSAAS_POSTGRES_IMAGE}"
: "${AGENTSAAS_REDIS_IMAGE:?Set digest-pinned AGENTSAAS_REDIS_IMAGE}"
: "${COSIGN_PUBLIC_KEY:?Set the vendor Cosign public key used to verify every image}"

command -v docker >/dev/null
command -v cosign >/dev/null
command -v syft >/dev/null
[[ "$VERSION" != "latest" ]]
[[ "$VERSION" =~ ^[A-Za-z0-9._-]+$ ]] || { echo "Unsafe release version" >&2; exit 1; }
BUNDLE="$OUTPUT_DIR/agentsaas-$VERSION"
rm -rf "$BUNDLE"
mkdir -p "$BUNDLE/images" "$BUNDLE/sbom" "$BUNDLE/deploy" "$BUNDLE/scripts" "$BUNDLE/desktop" "$BUNDLE/app/core"

for spec in \
  "api|$AGENTSAAS_API_IMAGE" \
  "admin|$AGENTSAAS_ADMIN_IMAGE" \
  "hermes-runtime|$AGENTSAAS_HERMES_RUNTIME_IMAGE" \
  "caddy|$AGENTSAAS_CADDY_IMAGE" \
  "postgres|$AGENTSAAS_POSTGRES_IMAGE" \
  "redis|$AGENTSAAS_REDIS_IMAGE"
do
  name="${spec%%|*}"; image="${spec#*|}"
  [[ "$image" =~ @sha256:[0-9a-f]{64}$ ]] || { echo "$name image is not digest-pinned" >&2; exit 1; }
  docker pull "$image"
  docker save "$image" | gzip -n > "$BUNDLE/images/$name.tar.gz"
  syft "$image" -o spdx-json="$BUNDLE/sbom/$name.spdx.json"
  cosign verify --key "$COSIGN_PUBLIC_KEY" "$image" >/dev/null
done

cp docker-compose.release.yml "$BUNDLE/compose.yml"
cp deploy/Caddyfile deploy/agentsaas.sh deploy/backup.sh deploy/restore.sh \
  deploy/production_readiness_check.sh deploy/install_offline.sh deploy/upgrade.sh "$BUNDLE/deploy/"
cp scripts/verify_release_bundle.py "$BUNDLE/scripts/"
cp app/__init__.py "$BUNDLE/app/"
cp app/core/__init__.py app/core/release_manifest.py "$BUNDLE/app/core/"
[[ -n "${AGENTSAAS_DESKTOP_ARTIFACT:-}" ]] && cp "$AGENTSAAS_DESKTOP_ARTIFACT" "$BUNDLE/desktop/"

python scripts/build_release_manifest.py \
  --bundle-dir "$BUNDLE" --version "$VERSION" \
  --api-image "$AGENTSAAS_API_IMAGE" --admin-image "$AGENTSAAS_ADMIN_IMAGE" \
  --runtime-image "$AGENTSAAS_HERMES_RUNTIME_IMAGE" \
  --caddy-image "$AGENTSAAS_CADDY_IMAGE" --postgres-image "$AGENTSAAS_POSTGRES_IMAGE" \
  --redis-image "$AGENTSAAS_REDIS_IMAGE" \
  --desktop-version "${AGENTSAAS_DESKTOP_VERSION:-$VERSION}" \
  --schema-revision "${AGENTSAAS_SCHEMA_REVISION:?Set AGENTSAAS_SCHEMA_REVISION}" \
  --schema-compatible-from "${AGENTSAAS_SCHEMA_COMPATIBLE_FROM:-$AGENTSAAS_SCHEMA_REVISION}"
cosign sign-blob --yes --key "$COSIGN_KEY" --output-signature "$BUNDLE/release-manifest.sig" "$BUNDLE/release-manifest.json"
tar -C "$OUTPUT_DIR" -czf "$OUTPUT_DIR/agentsaas-$VERSION-offline.tar.gz" "agentsaas-$VERSION"
echo "Offline release bundle: $OUTPUT_DIR/agentsaas-$VERSION-offline.tar.gz"
