from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.schemas.mcp import McpServerUpdate, ProfileMcpBindingUpsert
from app.services.mcp_connection_service import McpCredentialService, mcp_auth_headers, tools_schema_hash
from app.services.mcp_security import McpEndpointRejected, validate_mcp_url
from app.services.mcp_policy_resolver import effective_mcp_tools


@pytest.mark.parametrize(
    "url",
    [
        "http://mcp.example.com/mcp",
        "https://localhost/mcp",
        "https://127.0.0.1/mcp",
        "https://10.0.0.1/mcp",
        "https://169.254.169.254/latest/meta-data",
        "https://user:password@mcp.example.com/mcp",
        "https://mcp.example.com/mcp#fragment",
    ],
)
def test_mcp_url_rejects_unsafe_endpoints(url):
    with pytest.raises(McpEndpointRejected):
        validate_mcp_url(url)


def test_mcp_url_accepts_and_normalizes_https_endpoint():
    assert validate_mcp_url(" HTTPS://MCP.Example.com/mcp ") == "https://mcp.example.com/mcp"


def test_mcp_credentials_are_encrypted_and_hint_does_not_reveal_secret(monkeypatch):
    from cryptography.fernet import Fernet

    service = McpCredentialService()
    service._fernet = Fernet(Fernet.generate_key())
    encrypted = service.encrypt("secret-value-1234")
    assert encrypted != "secret-value-1234"
    assert service.decrypt(encrypted) == "secret-value-1234"
    assert service.hint("secret-value-1234") == "...1234"


def test_mcp_auth_headers_follow_server_auth_type():
    bearer = SimpleNamespace(auth_type="bearer", api_key_header="Authorization")
    api_key = SimpleNamespace(auth_type="api_key", api_key_header="X-API-Key")
    no_auth = SimpleNamespace(auth_type="none", api_key_header="Authorization")
    assert mcp_auth_headers(bearer, "token") == {"Authorization": "Bearer token"}
    assert mcp_auth_headers(api_key, "key") == {"X-API-Key": "key"}
    assert mcp_auth_headers(no_auth, None) == {}


def test_profile_mcp_binding_requires_explicit_allowed_tools_and_approval_subset():
    payload = ProfileMcpBindingUpsert(
        server_id="00000000-0000-0000-0000-000000000001",
        allowed_tools=["list_issues", "list_issues", "create_issue"],
        approval_required_tools=["create_issue"],
    )
    assert payload.allowed_tools == ["list_issues", "create_issue"]
    with pytest.raises(ValueError):
        ProfileMcpBindingUpsert(
            server_id="00000000-0000-0000-0000-000000000001",
            allowed_tools=["list_issues"],
            approval_required_tools=["delete_issue"],
        )


def test_tools_schema_hash_is_stable():
    tools = [{"name": "one", "description": "", "input_schema": {"type": "object"}}]
    assert tools_schema_hash(tools) == tools_schema_hash(list(tools))


def test_effective_mcp_tools_are_an_explicit_intersection():
    server_tools = [{"name": "list"}, {"name": "create"}, {"name": "new_tool"}]
    connection_tools = [{"name": "list"}, {"name": "create"}]
    assert effective_mcp_tools(["list", "create", "new_tool"], server_tools, connection_tools) == ["list", "create"]
    assert effective_mcp_tools([], server_tools, connection_tools) == []


def test_mcp_update_refreshes_server_generated_timestamp(monkeypatch):
    import asyncio
    import app.api.mcp_admin as mcp_admin_api

    connection = SimpleNamespace(
        owner_type="platform",
        encrypted_credentials=None,
        status="connected",
        is_active=True,
        discovered_tools=[],
        tools_schema_hash="",
        last_checked_at=None,
        last_error=None,
    )
    server = SimpleNamespace(
        id=uuid4(),
        slug="test-mcp",
        auth_type="none",
        credential_mode="platform",
        connections=[connection],
        discovered_tools=[],
        tools_schema_hash="",
        last_checked_at=None,
        last_error=None,
    )
    admin = SimpleNamespace(id=uuid4())

    class DbStub:
        refreshed = False

        def add(self, _item):
            return None

        async def flush(self):
            return None

        async def refresh(self, item, attribute_names=None):
            assert item is server
            assert attribute_names == ["updated_at"]
            self.refreshed = True

    db = DbStub()

    async def load_server(*_args):
        return server

    async def discover(*_args):
        return None

    monkeypatch.setattr(mcp_admin_api, "_server_with_relations", load_server)
    monkeypatch.setattr(mcp_admin_api, "_discover_server", discover)
    monkeypatch.setattr(mcp_admin_api, "_server_payload", lambda _item: {"refreshed": db.refreshed})

    result = asyncio.run(mcp_admin_api.update_mcp_server(
        server.id,
        McpServerUpdate(description="updated"),
        db,
        admin,
    ))

    assert result == {"refreshed": True}
    assert server.description == "updated"


def test_available_platform_mcp_reports_effective_admin_outage():
    from app.api.mcp_user import _connection_payload

    user_connection = SimpleNamespace(
        id=uuid4(),
        status="connected",
        credential_hint=None,
        last_checked_at=None,
        last_error=None,
    )
    platform_connection = SimpleNamespace(
        status="error",
        is_active=False,
        last_checked_at=None,
        last_error="MCP server hostname could not be resolved",
    )
    server = SimpleNamespace(credential_mode="platform")

    payload = _connection_payload(server, user_connection, platform_connection)

    assert payload["status"] == "error"
    assert payload["last_error"] == "MCP server hostname could not be resolved"


def test_available_platform_mcp_preserves_user_status_when_admin_is_ready():
    from app.api.mcp_user import _connection_payload

    user_connection = SimpleNamespace(
        id=uuid4(),
        status="connected",
        credential_hint=None,
        last_checked_at=None,
        last_error=None,
    )
    platform_connection = SimpleNamespace(
        status="connected",
        is_active=True,
        last_checked_at=None,
        last_error=None,
    )
    server = SimpleNamespace(credential_mode="platform")

    assert _connection_payload(server, user_connection, platform_connection)["status"] == "connected"
