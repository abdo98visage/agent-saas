"""Validation for immutable on-prem release manifests and offline bundles."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path


IMAGE_DIGEST = re.compile(r"^[a-zA-Z0-9._/:@-]+@sha256:[0-9a-f]{64}$")
SHA256 = re.compile(r"^[0-9a-f]{64}$")
REQUIRED_COMPONENTS = {"api", "admin", "hermes_runtime", "caddy", "postgres", "redis"}
REQUIRED_COMPATIBILITY = {"api", "desktop", "runtime", "schema", "mcp_contract"}


class ReleaseManifestError(ValueError):
    pass


def _safe_artifact_path(bundle_root: Path, relative: str) -> Path:
    if not relative or Path(relative).is_absolute():
        raise ReleaseManifestError(f"Unsafe artifact path: {relative}")
    target = (bundle_root / relative).resolve()
    root = bundle_root.resolve()
    if target != root and root not in target.parents:
        raise ReleaseManifestError(f"Artifact escapes bundle: {relative}")
    return target


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_release_manifest(data: dict, bundle_root: Path | None = None) -> dict:
    if data.get("schema") != "agentsaas.release.v1":
        raise ReleaseManifestError("Unsupported release manifest schema")
    version = str(data.get("version") or "").strip()
    if not version or version.lower() == "latest":
        raise ReleaseManifestError("Release version must be immutable")
    images = data.get("images") or {}
    if set(images) != REQUIRED_COMPONENTS:
        raise ReleaseManifestError("Release must contain all application and infrastructure images")
    for component, reference in images.items():
        if not IMAGE_DIGEST.fullmatch(str(reference)):
            raise ReleaseManifestError(f"Image {component} is not pinned by sha256 digest")
    compatibility = data.get("compatibility") or {}
    missing = REQUIRED_COMPATIBILITY - set(compatibility)
    if missing:
        raise ReleaseManifestError(f"Missing compatibility fields: {', '.join(sorted(missing))}")
    if compatibility.get("terminal_code_execution") != "prohibited":
        raise ReleaseManifestError("Release policy must prohibit Terminal and Code Execution")
    if data.get("license_mode") not in {"perpetual_offline", "offline_grace"}:
        raise ReleaseManifestError("Release must declare a non-blocking offline license mode")
    artifacts = data.get("artifacts") or []
    if not artifacts:
        raise ReleaseManifestError("Release contains no verifiable artifacts")
    seen = set()
    for artifact in artifacts:
        relative = str(artifact.get("path") or "")
        expected = str(artifact.get("sha256") or "").lower()
        if relative in seen or not SHA256.fullmatch(expected):
            raise ReleaseManifestError(f"Invalid artifact entry: {relative}")
        seen.add(relative)
        if bundle_root is not None:
            path = _safe_artifact_path(bundle_root, relative)
            if not path.is_file() or sha256_file(path) != expected:
                raise ReleaseManifestError(f"Artifact checksum mismatch: {relative}")
    return data


def load_and_validate_release_manifest(path: Path, verify_artifacts: bool = True) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    return validate_release_manifest(data, path.parent if verify_artifacts else None)
