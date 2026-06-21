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


def test_dashboard_stats_exposes_operational_observability():
    source = inspect.getsource(admin_api.get_dashboard_stats)

    for token in [
        "total_runs_today",
        "run_failure_rate_today",
        "avg_latency_ms_today",
        "api_keys_over_70pct_budget",
        "key_budget_pressure",
        "employee_cost",
        "profile_usage",
    ]:
        assert token in source


def test_usage_report_and_provider_pricing_endpoints_exist():
    source = inspect.getsource(admin_api.get_usage_report)
    pricing_source = inspect.getsource(admin_api.upsert_provider_pricing)

    for token in [
        "employee_profiles",
        "summary",
        "total_tokens",
        "total_cost",
        "pricing",
    ]:
        assert token in source

    for token in [
        "monthly_price_usd",
        "monthly_token_allowance",
        "ProviderPricing",
    ]:
        assert token in pricing_source


def test_kpi_page_exposes_monthly_usage_analytics():
    with open("frontend/src/app/kpis/page.tsx", encoding="utf-8") as file:
        content = file.read()

    for token in [
        "Usage Analytics",
        "Employee Consumption This Month",
        "Agent Consumption This Month",
        "Employee x Agent Matrix",
        "getUsageReport",
    ]:
        assert token in content


def test_token_expiry_guards_exist_for_activation_and_telegram_binding():
    with open("app/api/auth.py", encoding="utf-8") as file:
        auth_content = file.read()
    with open("app/api/telegram.py", encoding="utf-8") as file:
        telegram_content = file.read()

    assert "invite_token_expires_at" in auth_content
    assert "Invite token expired" in auth_content
    assert "binding_token_expires_at" in telegram_content
    assert "Bind code expired" in telegram_content


def test_auth_and_websocket_use_revocable_single_use_tokens():
    with open("app/api/auth.py", encoding="utf-8") as file:
        auth_content = file.read()
    with open("app/api/websocket_chat.py", encoding="utf-8") as file:
        websocket_content = file.read()

    assert "token_version" in auth_content
    assert '"purpose": "ws"' in auth_content
    assert "consume_ws_ticket" in websocket_content
    assert 'payload.get("purpose") != "ws"' in websocket_content


def test_alerting_endpoints_and_service_exist():
    with open("app/api/admin.py", encoding="utf-8") as file:
        admin_content = file.read()
    with open("app/services/alert_service.py", encoding="utf-8") as file:
        alert_service_content = file.read()
    with open("app/celery_app.py", encoding="utf-8") as file:
        celery_content = file.read()
    with open("frontend/src/app/page.tsx", encoding="utf-8") as file:
        dashboard_content = file.read()

    assert "/monitoring/alerts" in admin_content
    assert "run_alert_evaluation" in admin_content
    assert "acknowledge_alert" in admin_content
    assert "collect_candidates" in alert_service_content
    assert "sync_candidates" in alert_service_content
    assert "pending_notifications" in alert_service_content
    assert "evaluate-platform-alerts" in celery_content
    assert "Active Alerts" in dashboard_content
