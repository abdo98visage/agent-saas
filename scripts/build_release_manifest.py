"""Build a canonical release manifest after images/SBOMs/artifacts have been produced."""
import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.release_manifest import sha256_file, validate_release_manifest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bundle-dir", required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--api-image", required=True)
    parser.add_argument("--admin-image", required=True)
    parser.add_argument("--runtime-image", required=True)
    parser.add_argument("--caddy-image", required=True)
    parser.add_argument("--postgres-image", required=True)
    parser.add_argument("--redis-image", required=True)
    parser.add_argument("--desktop-version", required=True)
    parser.add_argument("--schema-revision", required=True)
    parser.add_argument("--schema-compatible-from", default="")
    parser.add_argument("--mcp-contract", default="2025-06-18")
    parser.add_argument("--rollback-schema-compatible", action="store_true")
    args = parser.parse_args()
    root = Path(args.bundle_dir).resolve()
    manifest_path = root / "release-manifest.json"
    artifacts = []
    for path in sorted(item for item in root.rglob("*") if item.is_file() and item.name not in {"release-manifest.json", "release-manifest.sig"}):
        artifacts.append({"path": path.relative_to(root).as_posix(), "sha256": sha256_file(path), "size": path.stat().st_size})
    manifest = {
        "schema": "agentsaas.release.v1",
        "version": args.version,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "license_mode": "perpetual_offline",
        "images": {
            "api": args.api_image, "admin": args.admin_image, "hermes_runtime": args.runtime_image,
            "caddy": args.caddy_image, "postgres": args.postgres_image, "redis": args.redis_image,
        },
        "compatibility": {
            "api": args.version, "desktop": args.desktop_version, "runtime": args.version,
            "schema": args.schema_revision, "mcp_contract": args.mcp_contract,
            "schema_compatible_from": [item for item in args.schema_compatible_from.split(",") if item],
            "terminal_code_execution": "prohibited",
            "rollback_schema_compatible": args.rollback_schema_compatible,
        },
        "artifacts": artifacts,
    }
    validate_release_manifest(manifest, root)
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(manifest_path)


if __name__ == "__main__":
    main()
