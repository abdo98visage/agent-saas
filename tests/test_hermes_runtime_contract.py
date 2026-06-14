import inspect
from pathlib import Path

from app.api import admin as admin_api
from app import hermes_orchestrator_app
from app.models.profile import Profile
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

    assert payload["files"]["AGENTS.md"] == "# Agent"
    assert payload["files"]["soul.md"] == "Soul"
    assert "- copywriting" in payload["files"]["skills.md"]
    assert payload["files"]["system_prompt.md"] == "System"
    assert payload["profile"]["slug"] == "marketing"
    assert payload["profile"]["version"] == 3


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


async def test_orchestrator_sync_profile_writes_expected_files(tmp_path, monkeypatch):
    monkeypatch.setattr(hermes_orchestrator_app, "HERMES_WORKSPACE_ROOT", Path(tmp_path))
    monkeypatch.setattr(hermes_orchestrator_app, "ORCHESTRATOR_REQUIRE_SECRET", False)
    payload = {
        "profile": {"slug": "marketing", "version": 1},
        "files": {"AGENTS.md": "agent", "soul.md": "soul", "skills.md": "- skill"},
    }
    result = await hermes_orchestrator_app.sync_profile(payload)
    assert result["status"] == "synced"
    assert (tmp_path / "marketing" / "AGENTS.md").read_text(encoding="utf-8") == "agent"
    assert (tmp_path / "marketing" / "profile.json").exists()


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
