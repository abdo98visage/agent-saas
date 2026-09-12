import asyncio
from pathlib import Path

from app.celery_app import celery_app
from app.core.audit_context import correlation_id_context, trace_id_context
from app.main import app, request_logging_middleware
from app.models.audit_log import AuditExportCheckpoint, AuditLog, audit_category, redact_audit_details


def test_audit_details_recursively_redact_content_and_credentials():
    assert redact_audit_details({
        "profile": "sales",
        "prompt": "private prompt",
        "nested": {"api_key": "secret", "count": 2},
        "items": [{"message": "private message"}],
    }) == {
        "profile": "sales",
        "prompt": "[REDACTED]",
        "nested": {"api_key": "[REDACTED]", "count": 2},
        "items": [{"message": "[REDACTED]"}],
    }


def test_audit_schema_and_export_job_are_registered():
    assert "previous_hash" in AuditLog.__table__.columns
    assert "event_hash" in AuditLog.__table__.columns
    assert AuditExportCheckpoint.__table__.name == "audit_export_checkpoints"
    assert audit_category("mcp_server_created") == "connector"
    assert audit_category("login") == "identity"
    assert "export-audit-events" in celery_app.conf.beat_schedule
    assert "/api/metrics" in {route.path for route in app.routes}


def test_request_context_accepts_valid_ids_and_returns_trace_headers():
    class RequestStub:
        headers = {
            "X-Correlation-ID": "desktop-request-123",
            "traceparent": "00-0123456789abcdef0123456789abcdef-0123456789abcdef-01",
        }
        client = type("Client", (), {"host": "127.0.0.1"})()
        method = "GET"
        url = type("Url", (), {"path": "/api/status"})()

    class ResponseStub:
        status_code = 200
        headers = {}

    async def scenario():
        seen = {}

        async def downstream(_request):
            seen["correlation"] = correlation_id_context.get()
            seen["trace"] = trace_id_context.get()
            return ResponseStub()

        response = await request_logging_middleware(RequestStub(), downstream)
        assert seen == {
            "correlation": "desktop-request-123",
            "trace": "0123456789abcdef0123456789abcdef",
        }
        assert response.headers["X-Correlation-ID"] == "desktop-request-123"
        assert response.headers["traceparent"].startswith("00-0123456789abcdef0123456789abcdef-")
        assert correlation_id_context.get() is None
        assert trace_id_context.get() is None

    asyncio.run(scenario())


def test_audit_chain_migration_handles_concurrent_insert_order():
    migration = (
        Path(__file__).parents[1]
        / "migrations"
        / "versions"
        / "repair_audit_chain_order.py"
    ).read_text(encoding="utf-8")

    assert "NOT EXISTS (" in migration
    assert "child.previous_hash = candidate.event_hash" in migration
    assert "WITH RECURSIVE chain" in migration
    assert "ARRAY[event_hash]::text[]" in migration
    assert "forks = 0" in migration
