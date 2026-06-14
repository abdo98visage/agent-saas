"""Regression checks for admin API contracts that drive the admin UI."""

import inspect

from app.api import admin as admin_api
from app.schemas.admin import EmployeeUpdate, ProfileUpdate


def test_employee_update_schema_accepts_quota_fields():
    payload = EmployeeUpdate(max_tokens_per_day=12345, max_requests_per_day=321)
    assert payload.max_tokens_per_day == 12345
    assert payload.max_requests_per_day == 321


def test_profile_update_schema_accepts_agents_md():
    payload = ProfileUpdate(agents_md="# Updated profile")
    assert payload.agents_md == "# Updated profile"


def test_update_employee_handler_persists_quota_changes():
    source = inspect.getsource(admin_api.update_employee)
    assert "user.max_tokens_per_day = req.max_tokens_per_day" in source
    assert "user.max_requests_per_day = req.max_requests_per_day" in source


def test_list_profiles_returns_full_editable_fields():
    source = inspect.getsource(admin_api.list_profiles)
    assert '"agents_md": p.agents_md' in source
    assert '"system_prompt": p.system_prompt' in source


def test_profile_page_exposes_hermes_limits_and_tools():
    with open("frontend/src/app/profiles/page.tsx", encoding="utf-8") as file:
        content = file.read()

    for token in [
        "max_tokens_per_day",
        "max_requests_per_day",
        "daily_cost_budget",
        "allowed_providers",
        "allowed_mcp_servers",
        "allowed_tools",
        "approval_required_tools",
    ]:
        assert token in content


def test_api_keys_page_uses_owner_dropdowns():
    with open("frontend/src/app/api-keys/page.tsx", encoding="utf-8") as file:
        content = file.read()

    assert 'apiClient.get("/admin/employees")' in content
    assert 'apiClient.get("/admin/profiles")' in content
    assert "Select employee" in content
    assert "Select profile" in content
