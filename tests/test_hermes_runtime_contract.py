import inspect
from pathlib import Path
from tempfile import TemporaryDirectory

from app.api import admin as admin_api
from app.api import websocket_chat
from app import hermes_orchestrator_app
from app import local_hermes_runtime_app
from app.models.profile import Profile
from app.models.profile_user import ProfileUser
from app.models.skill_definition import SkillDefinition
from app.models.user import User
from app.schemas.admin import ApiKeyCreate, ProfileCreate
from app.services.agent_service import AgentService
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
    assert "Do not write files directly inside your own runtime working directory." in prompt


def test_local_runtime_prompt_disallows_hermes_workspace_as_user_project():
    prompt = local_hermes_runtime_app._build_prompt(
        {
            "employee": {"email": "employee@example.com"},
            "message": "Where are you and what project is open?",
            "workspace": {},
        }
    )
    assert "No desktop project is currently attached to this request." in prompt
    assert "Do not create or save files into Hermes runtime folders for the employee." in prompt


def test_local_runtime_runs_in_temporary_workspace(monkeypatch):
    captured = {}

    class FakeCompletedProcess:
        returncode = 0
        stdout = "hello"
        stderr = ""

    def fake_run(command, cwd, env, text, capture_output, timeout, check):
        captured["command"] = command
        captured["cwd"] = str(cwd)
        captured["hermes_home"] = env.get("HERMES_HOME")
        return FakeCompletedProcess()

    monkeypatch.setattr(local_hermes_runtime_app.subprocess, "run", fake_run)

    payload = {
        "profile": {"slug": "marketing"},
        "message": "Create a draft",
        "workspace": {"root_name": "customer-app"},
    }
    output = local_hermes_runtime_app._run_hermes(payload)

    assert output == "hello"
    assert "marketing" not in Path(captured["hermes_home"]).name
    assert captured["cwd"] == str(Path(captured["hermes_home"]) / "workspace")


def test_local_runtime_stages_profile_into_ephemeral_home():
    with TemporaryDirectory() as temp_dir:
        tmp_path = Path(temp_dir)
        source_profile = tmp_path / "source-profile"
        (source_profile / "workspace").mkdir(parents=True)
        (source_profile / "skills" / "copywriting").mkdir(parents=True)
        (source_profile / "workspace" / "AGENTS.md").write_text("agent rules", encoding="utf-8")
        (source_profile / "system_prompt.md").write_text("system", encoding="utf-8")
        (source_profile / "skills" / "copywriting" / "SKILL.md").write_text("# skill", encoding="utf-8")

        runtime_profile = tmp_path / "runtime-profile"
        runtime_workspace = local_hermes_runtime_app._stage_runtime_profile(source_profile, runtime_profile)

        assert runtime_workspace == runtime_profile / "workspace"
        assert (runtime_profile / "system_prompt.md").read_text(encoding="utf-8") == "system"
        assert (runtime_profile / "workspace" / "AGENTS.md").read_text(encoding="utf-8") == "agent rules"
        assert (runtime_profile / "skills" / "copywriting" / "SKILL.md").read_text(encoding="utf-8") == "# skill"


def test_local_runtime_sanitizes_internal_paths():
    text = "Saved to /tmp/hermes-run-123/profile/workspace/file.txt and /data/hermes/profiles/demo/workspace/file.txt"
    sanitized = local_hermes_runtime_app._sanitize_internal_paths(text)
    assert "/tmp/hermes-run-" not in sanitized
    assert "/data/hermes/profiles/" not in sanitized
    assert "[ephemeral-runtime-file]" in sanitized
    assert "[internal-runtime-path]" in sanitized


def test_local_runtime_renders_inline_artifact_for_text_file():
    with TemporaryDirectory() as temp_dir:
        runtime_workspace = Path(temp_dir)
        artifact = runtime_workspace / "check.txt"
        artifact.write_text("hello world", encoding="utf-8")
        rendered = local_hermes_runtime_app._render_inline_artifact_response(
            runtime_workspace,
            [artifact],
            "fallback",
        )
        assert "Filename: check.txt" in rendered
        assert "hello world" in rendered


def test_websocket_effective_project_context_uses_workspace_root():
    context = websocket_chat._effective_project_context(
        project_context="src/main.py:\nprint('ok')",
        workspace={"root_name": "AgentSaaS", "selected_files": ["src/main.py"]},
        workspace_supplied=True,
    )
    assert "Desktop active project root: AgentSaaS" in context
    assert "Do not substitute Hermes runtime folders" in context
    assert "Desktop selected files" in context


def test_websocket_effective_project_context_reports_no_project():
    context = websocket_chat._effective_project_context(
        project_context=None,
        workspace={"root_name": "", "selected_files": []},
        workspace_supplied=True,
    )
    assert "No desktop project is currently selected." in context
    assert "instead of inspecting Hermes internal folders" in context


async def test_agent_service_prefers_lowest_priority_profile_by_default():
    user = User(id="00000000-0000-0000-0000-000000000001", email="employee@example.com", role="employee")
    accounting = Profile(name="ايجنت المحاسبة", slug="accounting-agent", is_active=True)
    marketing = Profile(name="ايجنت التسويق", slug="marketing-agent", is_active=True)
    accounting_assignment = ProfileUser(user_id=user.id, profile_id="1", priority=0)
    marketing_assignment = ProfileUser(user_id=user.id, profile_id="2", priority=2)

    class FakeResult:
        def __init__(self, scalar=None, rows=None):
            self._scalar = scalar
            self._rows = rows or []

        def scalar_one_or_none(self):
            return self._scalar

        def all(self):
            return self._rows

    class FakeDb:
        def __init__(self):
            self.calls = 0

        async def execute(self, _query):
            self.calls += 1
            if self.calls == 1:
                return FakeResult(scalar=user)
            return FakeResult(rows=[(accounting_assignment, accounting), (marketing_assignment, marketing)])

    resolved = await AgentService().resolve_user_profile(FakeDb(), user.id, profile_name=None)
    assert resolved.name == "ايجنت المحاسبة"


async def test_agent_service_resolves_profile_by_slug():
    user = User(id="00000000-0000-0000-0000-000000000001", email="employee@example.com", role="employee")
    accounting = Profile(name="ايجنت المحاسبة", slug="accounting-agent", is_active=True)
    assignment = ProfileUser(user_id=user.id, profile_id="1", priority=0)

    class FakeResult:
        def __init__(self, scalar=None, rows=None):
            self._scalar = scalar
            self._rows = rows or []

        def scalar_one_or_none(self):
            return self._scalar

        def all(self):
            return self._rows

    class FakeDb:
        def __init__(self):
            self.calls = 0

        async def execute(self, _query):
            self.calls += 1
            if self.calls == 1:
                return FakeResult(scalar=user)
            return FakeResult(rows=[(assignment, accounting)])

    resolved = await AgentService().resolve_user_profile(FakeDb(), user.id, profile_name="accounting-agent")
    assert resolved.name == "ايجنت المحاسبة"
