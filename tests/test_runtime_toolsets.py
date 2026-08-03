import asyncio
import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml
import app.local_hermes_runtime_app as runtime_app

from app.core.runtime_policy import SAFE_RUNTIME_TOOLSETS, normalize_runtime_toolsets
from app.local_hermes_runtime_app import (
    _config_yaml,
    _mcp_tool_identity,
    _mcp_proxy_runs,
    _normalized_server_usage,
    _pending_approvals,
    _register_mcp_proxy,
    _runtime_env,
    _run_hermes_server_events,
    proxy_mcp_request,
    respond_approval,
)
from app.schemas.admin import ProfileCreate
from starlette.requests import Request


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


def test_runtime_approval_response_resolves_only_pending_decision():
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
        finally:
            _pending_approvals.pop(key, None)

    asyncio.run(scenario())
