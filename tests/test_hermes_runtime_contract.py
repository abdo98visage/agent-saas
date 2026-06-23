import inspect
from pathlib import Path
from tempfile import TemporaryDirectory

from app.api import admin as admin_api
from app import hermes_orchestrator_app
from app import local_hermes_runtime_app
from app.models.profile import Profile
from app.models.skill_definition import SkillDefinition
from app.schemas.admin import ApiKeyCreate, ProfileCreate
from app.services.hermes_profile_sync import build_profile_sync_payload
from app.services.hermes_orchestrator import HermesOrchestratorClient


def test_profile_create_defaults_to_hermes_runtime():
    payload = ProfileCreate(name="Marketing", slug="marketing")
    assert payload.runtime_type == "hermes"


def test_api_key_create_supports_profile_owner():
    payload = ApiKeyCreate(
        owner_type="profile",
        profile_id="00000000-0000-0000-0000-000000000001",
        provider="minimax",
        api_key="sk-123456789",
    )
    assert payload.owner_type == "profile"


def test_profile_sync_payload_generates_hermes_files():
    profile = Profile(
        name="Marketing",
        slug="marketing",
        agents_md="# Agent",
        soul_md="Soul",
        skills=["copywriting", "campaigns"],
        system_prompt="System",
    )
    profile.version = 3
    payload = build_profile_sync_payload(profile)

    assert payload["files"]["workspace/AGENTS.md"] == "# Agent"
    assert payload["files"]["SOUL.md"] == "Soul"
    assert payload["files"]["system_prompt.md"] == "System"
    assert "copywriting" in payload["files"]["skills/platform-profile/SKILL.md"]
    assert payload["files"]["skills/copywriting/SKILL.md"]
    assert payload["files"]["skills/campaigns/SKILL.md"]
    assert payload["profile"]["slug"] == "marketing"
    assert payload["profile"]["version"] == 3


def test_profile_sync_payload_uses_real_skill_definition_content():
    profile = Profile(
        name="Marketing",
        slug="marketing",
        skills=["copywriting"],
    )
    skill = SkillDefinition(
        name="Copywriting",
        slug="copywriting",
        description="Write persuasive launch copy",
        instructions_md="# Copywriting\nAlways lead with value and a CTA.",
    )

    payload = build_profile_sync_payload(profile, [skill])
    skill_md = payload["files"]["skills/copywriting/SKILL.md"]

    assert "name: Copywriting" in skill_md
    assert "description: Write persuasive launch copy" in skill_md
    assert "# Copywriting" in skill_md
    assert "Always lead with value and a CTA." in skill_md


async def test_unconfigured_hermes_orchestrator_status_is_safe():
    client = HermesOrchestratorClient(base_url="")
    status = await client.status()
    assert status["status"] == "not_configured"
    assert status["installed"] is False


def test_admin_exposes_hermes_lifecycle_endpoints():
    source = inspect.getsource(admin_api)
    assert '@router.get("/hermes/status")' in source
    assert '@router.post("/hermes/install")' in source
    assert '@router.post("/profiles/{profile_id}/sync")' in source


async def test_orchestrator_sync_profile_writes_expected_files(monkeypatch):
    with TemporaryDirectory() as temp_dir:
        tmp_path = Path(temp_dir)
        monkeypatch.setattr(hermes_orchestrator_app, "HERMES_WORKSPACE_ROOT", tmp_path)
        monkeypatch.setattr(hermes_orchestrator_app, "ORCHESTRATOR_REQUIRE_SECRET", False)
        payload = {
            "profile": {"slug": "marketing", "version": 1},
            "files": {
                "workspace/AGENTS.md": "agent",
                "SOUL.md": "soul",
                "skills/platform-profile/SKILL.md": "# platform skill",
            },
        }
        result = await hermes_orchestrator_app.sync_profile(payload)
        assert result["status"] == "synced"
        assert (tmp_path / "marketing" / "workspace" / "AGENTS.md").read_text(encoding="utf-8") == "agent"
        assert (tmp_path / "marketing" / "SOUL.md").read_text(encoding="utf-8") == "soul"
        assert (tmp_path / "marketing" / "skills" / "platform-profile" / "SKILL.md").exists()
        assert (tmp_path / "marketing" / "profile.json").exists()


async def test_orchestrator_sync_profile_removes_stale_skill_artifacts(monkeypatch):
    with TemporaryDirectory() as temp_dir:
        tmp_path = Path(temp_dir)
        workspace = tmp_path / "marketing"
        stale_skill = workspace / "skills" / "legacy-skill" / "SKILL.md"
        stale_skill.parent.mkdir(parents=True, exist_ok=True)
        stale_skill.write_text("old", encoding="utf-8")

        monkeypatch.setattr(hermes_orchestrator_app, "HERMES_WORKSPACE_ROOT", tmp_path)
        monkeypatch.setattr(hermes_orchestrator_app, "ORCHESTRATOR_REQUIRE_SECRET", False)

        payload = {
            "profile": {"slug": "marketing", "version": 2},
            "files": {
                "skills/new-skill/SKILL.md": "# new skill",
            },
        }
        await hermes_orchestrator_app.sync_profile(payload)

        assert not stale_skill.exists()
        assert (workspace / "skills" / "new-skill" / "SKILL.md").read_text(encoding="utf-8") == "# new skill"


async def test_orchestrator_requires_secret_when_enabled(monkeypatch):
    monkeypatch.setattr(hermes_orchestrator_app, "ORCHESTRATOR_REQUIRE_SECRET", True)
    monkeypatch.setattr(hermes_orchestrator_app, "ORCHESTRATOR_SECRET", "")
    try:
        hermes_orchestrator_app._authorize(None)
    except Exception as exc:
        assert getattr(exc, "status_code", None) == 503
    else:
        raise AssertionError("orchestrator accepted requests without a configured secret")


async def test_orchestrator_has_healthz_for_container_healthcheck():
    result = await hermes_orchestrator_app.healthz()
    assert result["status"] == "healthy"


async def test_orchestrator_supports_externally_managed_runtime(monkeypatch):
    monkeypatch.setattr(hermes_orchestrator_app, "ORCHESTRATOR_REQUIRE_SECRET", False)
    monkeypatch.setattr(hermes_orchestrator_app, "HERMES_MANAGED_EXTERNALLY", True)

    async def fake_health():
        return {"ok": True, "status_code": 200}

    monkeypatch.setattr(hermes_orchestrator_app, "_hermes_health", fake_health)
    result = await hermes_orchestrator_app.status()
    assert result["managed_externally"] is True
    assert result["running"] is True
    assert result["run_health"] == "healthy"


async def test_orchestrator_run_proxy_normalizes_hermes_response(monkeypatch):
    monkeypatch.setattr(hermes_orchestrator_app, "ORCHESTRATOR_REQUIRE_SECRET", False)

    class FakeResponse:
        headers = {"content-type": "application/json"}

        def raise_for_status(self):
            return None

        def json(self):
            return {
                "output": "hello from hermes",
                "tools": ["search"],
                "mcp_servers": ["filesystem"],
                "cost": 0.25,
            }

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def post(self, url, json):
            assert url.endswith("/runs")
            assert json["message"] == "hi"
            return FakeResponse()

    monkeypatch.setattr(hermes_orchestrator_app.httpx, "AsyncClient", FakeClient)
    result = await hermes_orchestrator_app.run_agent({"message": "hi"})
    assert result["content"] == "hello from hermes"
    assert result["tools_used"] == ["search"]
    assert result["mcp_servers_used"] == ["filesystem"]
    assert result["total_cost"] == 0.25


def test_local_runtime_normalizes_cowork_tool_request():
    result = local_hermes_runtime_app._normalize_cowork_response(
        '{"type":"tool_request","tool":"read_file","args":{"path":"app/auth.py"}}'
    )
    assert result["type"] == "tool_request"
    assert result["tool"] == "read_file"
    assert result["args"]["path"] == "app/auth.py"
    assert result["request_id"]


def test_local_runtime_normalizes_cowork_apply_request():
    result = local_hermes_runtime_app._normalize_cowork_response(
        '{"type":"apply_request","summary":"Update auth","changes":[{"action":"update","path":"app/auth.py","content":"print(1)"}]}'
    )
    assert result["type"] == "apply_request"
    assert result["summary"] == "Update auth"
    assert result["changes"][0]["action"] == "update"


def test_local_runtime_falls_back_to_assistant_final_for_plain_text():
    result = local_hermes_runtime_app._normalize_cowork_response("hello from hermes")
    assert result == {"type": "assistant_final", "content": "hello from hermes"}


def test_local_runtime_builds_cowork_prompt_with_transcript():
    prompt = local_hermes_runtime_app._build_prompt(
        {
            "employee": {"email": "employee@example.com"},
            "message": "Refactor auth",
            "workspace": {"root_name": "my-project", "selected_files": ["app/auth.py"]},
            "cowork": {
                "protocol": "cowork_v1",
                "transcript": [
                    {"type": "tool_request", "tool": "read_file", "args": {"path": "app/auth.py"}},
                    {"type": "tool_result", "ok": True, "result": {"path": "app/auth.py", "content": "x"}},
                ],
            },
        }
    )
    assert "Cowork protocol mode is enabled." in prompt
    assert "tool_request read_file" in prompt
    assert "my-project" in prompt
