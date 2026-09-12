import asyncio
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest
import yaml
import app.local_hermes_runtime_app as runtime_app
from fastapi import HTTPException

from app.core.runtime_policy import SAFE_RUNTIME_TOOLSETS, effective_profile_policy, normalize_runtime_toolsets
from app.local_hermes_runtime_app import (
    _authorize_runtime,
    _cleanup_stale_runtime_directories,
    _config_yaml,
    _mcp_tool_identity,
    _mcp_proxy_runs,
    _normalized_server_usage,
    _pending_approvals,
    _register_mcp_proxy,
    _runtime_env,
    _run_hermes_server_events,
    _has_explicit_mcp_intent,
    _stage_runtime_profile,
    proxy_mcp_request,
    respond_approval,
)
from app.schemas.admin import ProfileCreate
from starlette.requests import Request


def test_profile_defaults_to_safe_runtime_toolsets():
    profile = ProfileCreate(name="Safe", slug="safe")
    assert profile.runtime_toolsets == SAFE_RUNTIME_TOOLSETS


def test_runtime_startup_cleanup_removes_only_stale_run_directories(tmp_path: Path):
    stale = tmp_path / "hermes-run-stale"
    unrelated = tmp_path / "keep-me"
    outside = tmp_path / "outside"
    stale.mkdir()
    unrelated.mkdir()
    outside.mkdir()
    (stale / "artifact.txt").write_text("temporary", encoding="utf-8")
    link = tmp_path / "hermes-run-link"
    try:
        link.symlink_to(outside, target_is_directory=True)
    except OSError:
        link = None

    removed = _cleanup_stale_runtime_directories(tmp_path)

    assert removed == (2 if link is not None else 1)
    assert not stale.exists()
    assert unrelated.is_dir()
    assert outside.is_dir()


def test_profile_rejects_unknown_runtime_toolsets():
    with pytest.raises(ValueError, match="Unsupported runtime toolsets"):
        ProfileCreate(name="Unsafe", slug="unsafe", runtime_toolsets=["shell"])


@pytest.mark.parametrize("toolset", ["terminal", "code_execution"])
def test_profile_rejects_prohibited_execution_toolsets(toolset: str):
    with pytest.raises(ValueError, match="Prohibited runtime toolsets"):
        ProfileCreate(name="Unsafe", slug="unsafe", runtime_toolsets=[toolset])


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
    assert "terminal:\n" not in config


def test_runtime_toolsets_are_deduplicated():
    assert normalize_runtime_toolsets(["web", "web", "clarify"]) == ["web", "clarify"]


def test_effective_profile_policy_is_versioned_and_never_allows_execution_tools():
    class ProfilePolicyFixture:
        id = "profile-1"
        version = 4
        runtime_type = "hermes"
        runtime_toolsets = ["web", "clarify"]
        allowed_tools = ["read_file", "read_file"]
        approval_required_tools = ["read_file"]

    policy = effective_profile_policy(ProfilePolicyFixture())
    assert policy["policy_id"] == "profile-profile-1-v4"
    assert policy["runtime_toolsets"] == ["web", "clarify"]
    assert policy["prohibited_toolsets"] == ["code_execution", "terminal"]
    assert policy["allowed_tools"] == ["read_file"]


def test_runtime_private_api_requires_its_own_secret(monkeypatch):
    monkeypatch.setattr(runtime_app, "RUNTIME_REQUIRE_SECRET", True)
    monkeypatch.setattr(runtime_app, "RUNTIME_SECRET", "runtime-secret-123")
    with pytest.raises(Exception) as missing:
        _authorize_runtime(None)
    assert getattr(missing.value, "status_code", None) == 403
    with pytest.raises(Exception) as wrong:
        _authorize_runtime("orchestrator-secret-456")
    assert getattr(wrong.value, "status_code", None) == 403
    _authorize_runtime("runtime-secret-123")


def test_each_runtime_run_uses_an_isolated_ephemeral_workspace(tmp_path: Path):
    source = tmp_path / "source"
    (source / "workspace").mkdir(parents=True)
    (source / "workspace" / "AGENTS.md").write_text("safe instructions", encoding="utf-8")
    (source / "workspace" / "persistent-secret.txt").write_text("must not copy", encoding="utf-8")

    with tempfile.TemporaryDirectory(prefix="runtime-a-") as root_a, tempfile.TemporaryDirectory(
        prefix="runtime-b-"
    ) as root_b:
        workspace_a = _stage_runtime_profile(source, Path(root_a) / "profile")
        workspace_b = _stage_runtime_profile(source, Path(root_b) / "profile")
        (workspace_a / "generated.txt").write_text("run a", encoding="utf-8")

        assert workspace_a != workspace_b
        assert (workspace_b / "AGENTS.md").read_text(encoding="utf-8") == "safe instructions"
        assert not (workspace_b / "generated.txt").exists()
        assert not (workspace_a / "persistent-secret.txt").exists()
        assert not (workspace_b / "persistent-secret.txt").exists()
        removed_a = Path(root_a)
        removed_b = Path(root_b)

    assert not removed_a.exists()
    assert not removed_b.exists()


def test_runtime_recognizes_current_hermes_mcp_tool_names():
    servers = [{"slug": "context7-live-test", "allowed_tools": ["resolve-library-id"]}]
    assert _mcp_tool_identity(
        "mcp__context7_live_test__resolve_library_id",
        servers,
    ) == ("context7-live-test", "resolve-library-id")


def test_runtime_mcp_config_filters_tools_and_keeps_secret_out_of_yaml(tmp_path: Path):
    payload = {
        "provider": "mock",
        "model": "mock",
        "profile": {"runtime_toolsets": []},
        "mcp_servers": [{
            "slug": "github",
            "url": "https://mcp.example.com/mcp",
            "auth_type": "bearer",
            "credential_env": "MCP_GITHUB_TOKEN",
            "credential": "super-secret",
            "allowed_tools": ["list_issues", "create_issue"],
        }],
    }
    config = _config_yaml(payload, tmp_path, tmp_path / "workspace")
    assert yaml.safe_load(config)["model"]["default"] == "mock"
    assert "mcp_discovery_timeout: 12.0" in config
    assert "platform_toolsets:\n  cli:\n    - github" in config
    assert "https://mcp.example.com/mcp" in config
    assert '"Authorization": "Bearer ${MCP_GITHUB_TOKEN}"' in config
    assert '        - "list_issues"' in config
    assert "super-secret" not in config
    assert "enabled: false" in config
    env = _runtime_env(payload, tmp_path)
    assert env["MCP_GITHUB_TOKEN"] == "super-secret"
    assert env["HERMES_TUI_TOOLSETS"] == "github"


def test_runtime_uses_only_run_scoped_model_proxy_token(tmp_path: Path):
    payload = {
        "provider": "openai",
        "model": "model",
        "api_key": "run-scoped-token",
        "provider_base_url": "http://hermes-orchestrator:8788/internal/model/v1/chat/completions",
        "profile": {"runtime_toolsets": []},
    }
    config = _config_yaml(payload, tmp_path, tmp_path / "workspace")
    env = _runtime_env(payload, tmp_path)
    assert "http://hermes-orchestrator:8788/internal/model/v1" in config
    assert env["OPENAI_API_KEY"] == "run-scoped-token"


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


def test_explicit_mcp_intent_recognizes_server_and_tool_names():
    payload = {
        "message": "Use Context7 to resolve-library-id for FastAPI",
        "mcp_servers": [{
            "name": "Context7",
            "slug": "context7",
            "allowed_tools": ["resolve-library-id"],
        }],
    }
    assert _has_explicit_mcp_intent(payload) is True
    assert _has_explicit_mcp_intent({**payload, "message": "Reply exactly ALIVE"}) is False


def test_passive_mcp_failure_retries_ordinary_chat_without_mcp(monkeypatch):
    calls = []

    async def fake_once(payload):
        calls.append(payload)
        if payload.get("mcp_servers"):
            raise RuntimeError("MCP discovery timed out")
        yield {"type": "delta", "content": "ALIVE"}
        yield {"type": "complete", "content": "ALIVE", "usage": {}}

    monkeypatch.setattr(runtime_app, "_run_hermes_server_events_once", fake_once)

    async def collect():
        return [event async for event in runtime_app._run_hermes_server_events({
            "message": "Reply exactly ALIVE",
            "project_context": "existing context",
            "mcp_servers": [{"name": "Context7", "slug": "context7", "allowed_tools": ["resolve-library-id"]}],
        })]

    events = asyncio.run(collect())
    assert [event["type"] for event in events] == ["delta", "complete"]
    assert calls[1]["mcp_servers"] == []
    assert "do not claim that an MCP tool was used" in calls[1]["project_context"]


def test_explicit_mcp_failure_is_not_silently_retried(monkeypatch):
    calls = []

    async def fake_once(payload):
        calls.append(payload)
        raise RuntimeError("MCP discovery timed out")
        yield  # pragma: no cover

    monkeypatch.setattr(runtime_app, "_run_hermes_server_events_once", fake_once)

    async def collect():
        return [event async for event in runtime_app._run_hermes_server_events({
            "message": "Use MCP Context7 now",
            "mcp_servers": [{"name": "Context7", "slug": "context7", "allowed_tools": ["resolve-library-id"]}],
        })]

    with pytest.raises(RuntimeError, match="MCP discovery timed out"):
        asyncio.run(collect())
    assert len(calls) == 1


def test_runtime_mcp_proxy_keeps_credentials_out_of_hermes_config(tmp_path: Path):
    payload = {
        "run_id": "run-1",
        "interactive_approvals": True,
        "provider": "openai",
        "model": "model",
        "profile": {"runtime_toolsets": []},
        "mcp_servers": [{
            "slug": "github",
            "url": "https://mcp.example.com/mcp",
            "auth_type": "bearer",
            "credential_env": "MCP_GITHUB_TOKEN",
            "credential": "super-secret",
            "allowed_tools": ["list_issues"],
            "approval_required_tools": ["list_issues"],
        }],
    }
    proxied, token = _register_mcp_proxy(payload)
    try:
        config = _config_yaml(proxied, tmp_path, tmp_path / "workspace")
        env = _runtime_env(proxied, tmp_path)
        assert "/internal/mcp/github" in config
        assert token in config
        assert "https://mcp.example.com/mcp" not in config
        assert "super-secret" not in config
        assert "MCP_GITHUB_TOKEN" not in env
        assert _mcp_proxy_runs[token]["servers"]["github"]["credential"] == "super-secret"
    finally:
        _mcp_proxy_runs.pop(token, None)


@pytest.mark.skipif(shutil.which("hermes") is None, reason="Hermes CLI is not installed")
def test_generated_mcp_config_is_accepted_by_hermes_cli(tmp_path: Path):
    payload = {
        "provider": "openai",
        "model": "model",
        "profile": {"runtime_toolsets": []},
        "mcp_servers": [{
            "slug": "catalog",
            "url": "http://127.0.0.1:8787/internal/mcp/catalog",
            "auth_type": "none",
            "proxy_token": "test-run-token",
            "allowed_tools": ["search"],
        }],
    }
    (tmp_path / "workspace").mkdir()
    (tmp_path / "config.yaml").write_text(
        _config_yaml(payload, tmp_path, tmp_path / "workspace"),
        encoding="utf-8",
    )
    env = {**os.environ, "HOME": str(tmp_path), "HERMES_HOME": str(tmp_path)}
    result = subprocess.run(
        [shutil.which("hermes"), "mcp", "list"],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )
    assert result.returncode == 0, result.stderr or result.stdout
    assert "catalog" in result.stdout


def test_noninteractive_mcp_proxy_denies_approval_tools_before_upstream():
    async def scenario():
        payload = {
            "run_id": "run-2",
            "interactive_approvals": False,
            "mcp_servers": [{
                "slug": "crm",
                "url": "https://mcp.example.com/mcp",
                "auth_type": "none",
                "credential": "",
                "allowed_tools": ["delete_contact"],
                "approval_required_tools": ["delete_contact"],
            }],
        }
        _, token = _register_mcp_proxy(payload)
        body = json.dumps({
            "jsonrpc": "2.0",
            "id": 7,
            "method": "tools/call",
            "params": {"name": "delete_contact", "arguments": {"id": "secret"}},
        }).encode()

        async def receive():
            return {"type": "http.request", "body": body, "more_body": False}

        request = Request({
            "type": "http",
            "method": "POST",
            "path": "/internal/mcp",
            "headers": [(b"content-type", b"application/json"), (b"x-agentsaas-mcp-run", token.encode())],
            "query_string": b"",
            "server": ("test", 80),
            "client": ("test", 1234),
            "scheme": "http",
        }, receive)
        try:
            response = await proxy_mcp_request("crm", request)
            parsed = json.loads(bytes(response.body))
            assert response.status_code == 200
            assert parsed["id"] == 7
            assert parsed["result"]["isError"] is True
            assert "secret" not in json.dumps(parsed)
        finally:
            _mcp_proxy_runs.pop(token, None)

    asyncio.run(scenario())


def test_interactive_mcp_proxy_waits_for_approval_then_forwards(monkeypatch):
    captured: dict = {}

    class FakeUpstream:
        status_code = 200
        headers = {"content-type": "application/json", "mcp-session-id": "session-1"}

        async def aiter_raw(self):
            yield b'{"jsonrpc":"2.0","id":8,"result":{"content":[]}}'

        async def aclose(self):
            return None

    class FakeClient:
        def __init__(self, **_kwargs):
            pass

        def build_request(self, method, url, headers, content):
            captured.update(method=method, url=url, headers=headers, content=content)
            return captured

        async def send(self, _request, stream=False):
            assert stream is True
            return FakeUpstream()

        async def aclose(self):
            return None

    async def safe_destination(url):
        return url

    monkeypatch.setattr(runtime_app, "validate_mcp_destination", safe_destination)
    monkeypatch.setattr(runtime_app.httpx, "AsyncClient", FakeClient)

    async def scenario():
        payload = {
            "run_id": "run-interactive",
            "interactive_approvals": True,
            "mcp_servers": [{
                "slug": "crm",
                "url": "https://mcp.example.com/mcp",
                "auth_type": "bearer",
                "credential": "remote-secret",
                "allowed_tools": ["update_contact"],
                "approval_required_tools": ["update_contact"],
            }],
        }
        _, token = _register_mcp_proxy(payload)
        body = json.dumps({
            "jsonrpc": "2.0",
            "id": 8,
            "method": "tools/call",
            "params": {"name": "update_contact", "arguments": {"id": 1}},
        }).encode()

        async def receive():
            return {"type": "http.request", "body": body, "more_body": False}

        request = Request({
            "type": "http",
            "method": "POST",
            "path": "/internal/mcp/crm",
            "headers": [(b"content-type", b"application/json"), (b"x-agentsaas-mcp-run", token.encode())],
            "query_string": b"",
            "server": ("test", 80),
            "client": ("test", 1234),
            "scheme": "http",
        }, receive)
        try:
            proxy_task = asyncio.create_task(proxy_mcp_request("crm", request))
            approval = await asyncio.wait_for(_mcp_proxy_runs[token]["approval_queue"].get(), timeout=1)
            assert not proxy_task.done()
            approval["future"].set_result("approve")
            response = await proxy_task
            response_bytes = b"".join([chunk async for chunk in response.body_iterator])
            assert response.status_code == 200
            assert b'"id":8' in response_bytes
            assert captured["headers"]["Authorization"] == "Bearer remote-secret"
            assert captured["url"] == "https://mcp.example.com/mcp"
        finally:
            _mcp_proxy_runs.pop(token, None)

    asyncio.run(scenario())


def test_runtime_approval_response_resolves_only_pending_decision(monkeypatch):
    monkeypatch.setattr(runtime_app, "RUNTIME_REQUIRE_SECRET", False)
    async def scenario():
        future = asyncio.get_running_loop().create_future()
        key = ("run-3", "approval-3")
        _pending_approvals[key] = future
        try:
            response = await respond_approval({
                "run_id": key[0],
                "approval_id": key[1],
                "decision": "approve",
            })
            assert response == {"status": "accepted", "decision": "approve"}
            assert await future == "approve"
            with pytest.raises(HTTPException) as replay:
                await respond_approval({
                    "run_id": key[0],
                    "approval_id": key[1],
                    "decision": "approve",
                })
            assert replay.value.status_code == 404
        finally:
            _pending_approvals.pop(key, None)

    asyncio.run(scenario())


def test_interactive_mcp_approval_timeout_denies_without_upstream(monkeypatch):
    monkeypatch.setattr(runtime_app.settings, "mcp_approval_timeout_seconds", 0.01)

    async def scenario():
        payload = {
            "run_id": "run-timeout",
            "interactive_approvals": True,
            "mcp_servers": [{
                "slug": "crm",
                "url": "https://mcp.example.com/mcp",
                "auth_type": "none",
                "credential": "",
                "allowed_tools": ["update_contact"],
                "approval_required_tools": ["update_contact"],
            }],
        }
        _, token = _register_mcp_proxy(payload)
        body = json.dumps({
            "jsonrpc": "2.0",
            "id": 9,
            "method": "tools/call",
            "params": {"name": "update_contact", "arguments": {"id": 1}},
        }).encode()

        async def receive():
            return {"type": "http.request", "body": body, "more_body": False}

        request = Request({
            "type": "http",
            "method": "POST",
            "path": "/internal/mcp/crm",
            "headers": [(b"content-type", b"application/json"), (b"x-agentsaas-mcp-run", token.encode())],
            "query_string": b"",
            "server": ("test", 80),
            "client": ("test", 1234),
            "scheme": "http",
        }, receive)
        try:
            response = await proxy_mcp_request("crm", request)
            assert response.status_code == 200
            assert b'"isError":true' in response.body
            assert b"denied by the user" in response.body
        finally:
            _mcp_proxy_runs.pop(token, None)

    asyncio.run(scenario())


def test_mcp_upstream_failure_during_tool_call_is_explicit(monkeypatch):
    class FailingClient:
        def __init__(self, **_kwargs):
            pass

        def build_request(self, *_args, **_kwargs):
            return object()

        async def send(self, *_args, **_kwargs):
            raise OSError("connection lost during MCP call")

        async def aclose(self):
            return None

    async def safe_destination(url):
        return url

    monkeypatch.setattr(runtime_app, "validate_mcp_destination", safe_destination)
    monkeypatch.setattr(runtime_app.httpx, "AsyncClient", FailingClient)

    async def scenario():
        payload = {
            "run_id": "run-mid-call",
            "interactive_approvals": True,
            "mcp_servers": [{
                "slug": "catalog",
                "url": "https://mcp.example.com/mcp",
                "auth_type": "none",
                "credential": "",
                "allowed_tools": ["search"],
                "approval_required_tools": [],
            }],
        }
        _, token = _register_mcp_proxy(payload)
        body = json.dumps({
            "jsonrpc": "2.0", "id": 10, "method": "tools/call",
            "params": {"name": "search", "arguments": {"q": "FastAPI"}},
        }).encode()

        async def receive():
            return {"type": "http.request", "body": body, "more_body": False}

        request = Request({
            "type": "http", "method": "POST", "path": "/internal/mcp/catalog",
            "headers": [(b"content-type", b"application/json"), (b"x-agentsaas-mcp-run", token.encode())],
            "query_string": b"", "server": ("test", 80), "client": ("test", 1234), "scheme": "http",
        }, receive)
        try:
            with pytest.raises(HTTPException) as failure:
                await proxy_mcp_request("catalog", request)
            assert failure.value.status_code == 502
            assert failure.value.detail == "MCP upstream request failed"
        finally:
            _mcp_proxy_runs.pop(token, None)

    asyncio.run(scenario())
