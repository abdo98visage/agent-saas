import base64
import binascii
import hashlib
import hmac
import json
import os
import re
import time
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

from app.core.config import settings


_DATA_URL = re.compile(
    r"^data:(image/(?:png|jpeg|gif|webp|bmp));base64,([A-Za-z0-9+/=\r\n]+)$",
    re.IGNORECASE,
)


def _detected_mime(data: bytes) -> str | None:
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if data.startswith((b"GIF87a", b"GIF89a")):
        return "image/gif"
    if len(data) >= 12 and data.startswith(b"RIFF") and data[8:12] == b"WEBP":
        return "image/webp"
    if data.startswith(b"BM"):
        return "image/bmp"
    return None


def normalize_image_attachments(items: Any) -> list[dict[str, Any]]:
    if items in (None, []):
        return []
    if not isinstance(items, list):
        raise ValueError("attachments must be a list")
    if len(items) > settings.attachment_max_count:
        raise ValueError(f"At most {settings.attachment_max_count} image attachments are allowed")

    normalized: list[dict[str, Any]] = []
    total_bytes = 0
    for item in items:
        if not isinstance(item, dict):
            raise ValueError("Invalid attachment")
        data_url = str(item.get("data_url") or "").strip()
        match = _DATA_URL.fullmatch(data_url)
        if not match:
            raise ValueError("Attachment must be a supported base64 image data URL")
        declared_mime = match.group(1).lower()
        try:
            raw = base64.b64decode(match.group(2), validate=True)
        except (binascii.Error, ValueError) as exc:
            raise ValueError("Attachment contains invalid base64 data") from exc
        detected_mime = _detected_mime(raw)
        if not detected_mime or detected_mime != declared_mime:
            raise ValueError("Attachment content does not match its image MIME type")
        if not raw or len(raw) > settings.attachment_max_bytes:
            raise ValueError("Attachment image is empty or too large")
        total_bytes += len(raw)
        if total_bytes > settings.attachment_total_max_bytes:
            raise ValueError("Combined attachment size is too large")

        reported_size = int(item.get("size_bytes") or 0)
        if reported_size and reported_size != len(raw):
            raise ValueError("Attachment size metadata does not match its content")
        normalized.append(
            {
                "name": str(item.get("name") or "image").strip()[:255] or "image",
                "mime_type": detected_mime,
                "data_url": data_url,
                "size_bytes": len(raw),
                "source": str(item.get("source") or "").strip()[:100] or None,
            }
        )
    return normalized


_EXTENSIONS = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/gif": ".gif",
    "image/webp": ".webp",
    "image/bmp": ".bmp",
}


def _decode_normalized_attachment(item: dict[str, Any]) -> bytes:
    match = _DATA_URL.fullmatch(str(item["data_url"]))
    if not match:
        raise ValueError("Invalid normalized attachment")
    return base64.b64decode(match.group(2), validate=True)


def persist_image_attachments(
    items: list[dict[str, Any]],
    user_id: UUID,
    session_id: UUID,
    message_id: UUID,
) -> list[dict[str, Any]]:
    """Persist validated image bytes and return JSONB-safe metadata only."""
    if not items:
        return []
    root = Path(settings.attachment_storage_root).resolve()
    object_dir = root / str(user_id) / str(session_id) / str(message_id)
    object_dir.mkdir(parents=True, exist_ok=True)
    records: list[dict[str, Any]] = []
    for item in items:
        raw = _decode_normalized_attachment(item)
        object_name = f"{uuid4()}{_EXTENSIONS[item['mime_type']]}"
        target = object_dir / object_name
        temp = object_dir / f".{object_name}.tmp"
        temp.write_bytes(raw)
        os.replace(temp, target)
        records.append({
            "name": item["name"],
            "mime_type": item["mime_type"],
            "size_bytes": len(raw),
            "source": item.get("source"),
            "sha256": hashlib.sha256(raw).hexdigest(),
            "object_key": target.relative_to(root).as_posix(),
        })
    return records


def delete_persisted_attachments(items: list[dict[str, Any]]) -> None:
    """Remove attachment files for a message that failed before completion."""
    root = Path(settings.attachment_storage_root).resolve()
    candidate_dirs: set[Path] = set()
    for item in items:
        object_key = str(item.get("object_key") or "")
        if not object_key:
            continue
        target = (root / object_key).resolve()
        if root not in target.parents:
            continue
        candidate_dirs.add(target.parent)
        target.unlink(missing_ok=True)
    for directory in sorted(candidate_dirs, key=lambda path: len(path.parts), reverse=True):
        current = directory
        while current != root and root in current.parents:
            try:
                current.rmdir()
            except OSError:
                break
            current = current.parent


def sign_attachment_path(object_key: str) -> str:
    expires_at = int(time.time()) + settings.attachment_url_ttl_seconds
    payload = json.dumps(
        {"key": object_key, "exp": expires_at},
        separators=(",", ":"),
    ).encode("utf-8")
    encoded = base64.urlsafe_b64encode(payload).rstrip(b"=").decode("ascii")
    signature = hmac.new(
        settings.secret_key.encode("utf-8"),
        encoded.encode("ascii"),
        hashlib.sha256,
    ).hexdigest()
    return f"/api/chat/attachments/{encoded}.{signature}"


def resolve_signed_attachment(token: str) -> Path:
    try:
        encoded, signature = token.rsplit(".", 1)
        expected = hmac.new(
            settings.secret_key.encode("utf-8"),
            encoded.encode("ascii"),
            hashlib.sha256,
        ).hexdigest()
        if not hmac.compare_digest(signature, expected):
            raise ValueError
        padded = encoded + "=" * (-len(encoded) % 4)
        payload = json.loads(base64.urlsafe_b64decode(padded).decode("utf-8"))
        if int(payload["exp"]) < int(time.time()):
            raise ValueError
        root = Path(settings.attachment_storage_root).resolve()
        target = (root / str(payload["key"])).resolve()
        if root not in target.parents or not target.is_file():
            raise ValueError
        return target
    except Exception as exc:
        raise ValueError("Invalid or expired attachment URL") from exc


def attachments_for_response(items: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    result = []
    for item in items or []:
        record = dict(item)
        if record.get("object_key"):
            record["signed_path"] = sign_attachment_path(str(record["object_key"]))
        result.append(record)
    return result
