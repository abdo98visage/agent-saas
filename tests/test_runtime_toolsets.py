import asyncio
from pathlib import Path

import pytest

from app.core.runtime_policy import SAFE_RUNTIME_TOOLSETS, normalize_runtime_toolsets
from app.local_hermes_runtime_app import (
    _config_yaml,
    _normalized_server_usage,
    _run_hermes_server_events,
)
from app.schemas.admin import ProfileCreate


def test_profile_defaults_to_safe_runtime_toolsets():
    profile = ProfileCreate(name="Safe", slug="safe")
    assert profile.runtime_toolsets == SAFE_RUNTIME_TOOLSETS


def test_profile_rejects_unknown_runtime_toolsets():
    with pytest.raises(ValueError, match="Unsupported runtime toolsets"):
        ProfileCreate(name="Unsafe", slug="unsafe", runtime_toolsets=["shell"])


def test_runtime_config_enables_only_profile_toolsets(tmp_path: Path):
    config = _config_yaml(
        {
            "provider": "mock",
            "model": "mock",
            "profile": {"runtime_toolsets": ["web", "clarify"]},
        },
        tmp_path,
        tmp_path / "workspace",
    )
    assert "platform_toolsets:\n  cli:\n    - web\n    - clarify" in config
    assert "    - terminal" in config
    assert "    - file" in config
    assert "    - code_execution" in config


def test_runtime_toolsets_are_deduplicated():
    assert normalize_runtime_toolsets(["web", "web", "clarify"]) == ["web", "clarify"]


def test_server_usage_is_normalized():
    assert _normalized_server_usage({"input": 12, "output": 5}) == {
        "input_tokens": 12,
        "output_tokens": 5,
    }


def test_mock_server_event_contract_has_delta_then_complete():
    async def collect():
        return [
            event
            async for event in _run_hermes_server_events({
                "provider": "mock",
                "message": "hello",
                "profile": {"name": "Safe"},
                "employee": {"full_name": "Tester"},
            })
        ]

    events = asyncio.run(collect())
    assert [event["type"] for event in events] == ["delta", "complete"]
    assert events[0]["content"] == events[1]["content"]
