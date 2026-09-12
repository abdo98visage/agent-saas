import asyncio
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

from app.api.websocket_chat import WebSocketUser, refresh_websocket_user


class ResultStub:
    def __init__(self, value):
        self.value = value

    def scalar_one_or_none(self):
        return self.value


class DbStub:
    def __init__(self, value):
        self.value = value

    async def execute(self, _query):
        return ResultStub(self.value)


def connected_user(user_id, token_version=2):
    return WebSocketUser(
        id=user_id,
        email="employee@example.com",
        full_name="Employee",
        department="qa",
        role="employee",
        is_active=True,
        is_activated=True,
        max_requests_per_day=100,
        max_tokens_per_day=100_000,
        token_version=token_version,
    )


def test_refresh_websocket_user_applies_live_quota_changes():
    user_id = uuid4()
    current = SimpleNamespace(
        id=user_id,
        email="employee@example.com",
        full_name="Employee",
        department="qa",
        role="employee",
        is_active=True,
        is_activated=True,
        max_requests_per_day=100_000,
        max_tokens_per_day=1_000_000_000,
        token_version=2,
    )
    refreshed = asyncio.run(refresh_websocket_user(DbStub(current), connected_user(user_id)))
    assert refreshed.max_tokens_per_day == 1_000_000_000
    assert refreshed.max_requests_per_day == 100_000


def test_refresh_websocket_user_rejects_disable_or_token_revocation():
    user_id = uuid4()
    disabled = SimpleNamespace(
        id=user_id,
        email="employee@example.com",
        full_name="Employee",
        department="qa",
        role="employee",
        is_active=False,
        is_activated=True,
        max_requests_per_day=100,
        max_tokens_per_day=100_000,
        token_version=2,
    )
    assert asyncio.run(refresh_websocket_user(DbStub(disabled), connected_user(user_id))) is None
    disabled.is_active = True
    disabled.token_version = 3
    assert asyncio.run(refresh_websocket_user(DbStub(disabled), connected_user(user_id))) is None


def test_websocket_checks_revocation_before_heartbeat_acknowledgement():
    source = (Path(__file__).parents[1] / "app" / "api" / "websocket_chat.py").read_text(encoding="utf-8")
    loop_start = source.index("# 3. Main message loop")
    refresh = source.index("live_user = await refresh_websocket_user", loop_start)
    heartbeat = source.index('if msg_type == "heartbeat":', loop_start)

    assert refresh < heartbeat
