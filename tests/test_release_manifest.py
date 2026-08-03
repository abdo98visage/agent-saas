import hashlib
import json

import pytest

from app.core.release_manifest import ReleaseManifestError, load_and_validate_release_manifest, validate_release_manifest


def valid_manifest(file_hash: str) -> dict:
    digest = "a" * 64
    return {
        "schema": "agentsaas.release.v1", "version": "1.2.3", "license_mode": "perpetual_offline",
        "images": {
            "api": f"registry.local/api@sha256:{digest}",
            "admin": f"registry.local/admin@sha256:{digest}",
            "hermes_runtime": f"registry.local/runtime@sha256:{digest}",
            "caddy": f"registry.local/caddy@sha256:{digest}",
            "postgres": f"registry.local/postgres@sha256:{digest}",
            "redis": f"registry.local/redis@sha256:{digest}",
        },
        "compatibility": {
            "api": "1.2.3", "desktop": "1.2.3", "runtime": "1.2.3", "schema": "evaluation_gates",
            "mcp_contract": "2025-06-18", "terminal_code_execution": "prohibited",
            "schema_compatible_from": ["tamper_evident_audit"], "rollback_schema_compatible": False,
        },
        "artifacts": [{"path": "sbom/api.spdx.json", "sha256": file_hash, "size": 2}],
    }


def test_release_manifest_requires_digests_and_prohibited_execution_policy(tmp_path):
    artifact = tmp_path / "sbom" / "api.spdx.json"
    artifact.parent.mkdir()
    artifact.write_bytes(b"{}")
    digest = hashlib.sha256(b"{}").hexdigest()
    manifest = valid_manifest(digest)
    (tmp_path / "release-manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    loaded = load_and_validate_release_manifest(tmp_path / "release-manifest.json")
    assert loaded["compatibility"]["terminal_code_execution"] == "prohibited"


def test_release_manifest_rejects_latest_unpinned_or_tampered_artifact(tmp_path):
    artifact = tmp_path / "sbom" / "api.spdx.json"
    artifact.parent.mkdir()
    artifact.write_bytes(b"tampered")
    manifest = valid_manifest("0" * 64)
    manifest["version"] = "latest"
    with pytest.raises(ReleaseManifestError):
        validate_release_manifest(manifest, tmp_path)
    manifest["version"] = "1.2.3"
    manifest["images"]["api"] = "registry.local/api:latest"
    with pytest.raises(ReleaseManifestError):
        validate_release_manifest(manifest, tmp_path)
    manifest["images"]["api"] = f"registry.local/api@sha256:{'a' * 64}"
    with pytest.raises(ReleaseManifestError, match="checksum"):
        validate_release_manifest(manifest, tmp_path)


def test_release_manifest_rejects_path_traversal(tmp_path):
    manifest = valid_manifest("0" * 64)
    manifest["artifacts"][0]["path"] = "../secret"
    with pytest.raises(ReleaseManifestError, match="escapes"):
        validate_release_manifest(manifest, tmp_path)
