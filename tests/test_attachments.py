import base64
from uuid import uuid4

import pytest

from app.core.config import settings
from app.services.attachments import (
    normalize_image_attachments,
    persist_image_attachments,
    resolve_signed_attachment,
    sign_attachment_path,
)


PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"production-test"


def _data_url(mime_type: str, payload: bytes = PNG_BYTES) -> str:
    encoded = base64.b64encode(payload).decode("ascii")
    return f"data:{mime_type};base64,{encoded}"


def test_attachment_is_validated_persisted_and_signed(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "attachment_storage_root", str(tmp_path))
    item = {
        "name": "evidence.png",
        "mime_type": "image/png",
        "data_url": _data_url("image/png"),
        "size_bytes": len(PNG_BYTES),
    }

    normalized = normalize_image_attachments([item])
    records = persist_image_attachments(
        normalized,
        user_id=uuid4(),
        session_id=uuid4(),
        message_id=uuid4(),
    )

    assert "data_url" not in records[0]
    token = sign_attachment_path(records[0]["object_key"]).rsplit("/", 1)[-1]
    assert resolve_signed_attachment(token).read_bytes() == PNG_BYTES


def test_attachment_rejects_declared_mime_mismatch():
    with pytest.raises(ValueError, match="does not match"):
        normalize_image_attachments([{"data_url": _data_url("image/jpeg")}])


def test_attachment_rejects_tampered_signature(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "attachment_storage_root", str(tmp_path))
    with pytest.raises(ValueError, match="Invalid or expired"):
        resolve_signed_attachment("payload.invalid-signature")
