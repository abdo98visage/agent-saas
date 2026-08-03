from datetime import datetime

import pytest

from app.celery_app import celery_app
from app.main import app
from app.main import rate_limit_middleware
from app.models.durable_task import DurableTask
from app.services.durable_task_service import (
    ACTIVE_TASK_STATES,
    TERMINAL_TASK_STATES,
    next_schedule_run,
    validate_schedule,
)


def test_durable_task_state_machine_is_explicit():
    assert ACTIVE_TASK_STATES == {"queued", "running", "waiting_approval", "paused"}
    assert TERMINAL_TASK_STATES == {"succeeded", "failed", "cancelled", "expired"}
    assert set(ACTIVE_TASK_STATES).isdisjoint(TERMINAL_TASK_STATES)


def test_daily_schedule_respects_business_timezone():
    next_run = next_schedule_run(
        "daily",
        None,
        "Asia/Riyadh",
        datetime(2026, 8, 3, 4, 30),
    )
    assert next_run == datetime(2026, 8, 3, 5, 0)


def test_cron_schedule_is_calculated_in_requested_timezone():
    next_run = next_schedule_run(
        "cron",
        "30 9 * * 1-5",
        "Europe/Berlin",
        datetime(2026, 8, 3, 6, 0),
    )
    assert next_run == datetime(2026, 8, 3, 7, 30)


@pytest.mark.parametrize(
    ("schedule_type", "expression", "timezone_name"),
    [("cron", "not cron", "UTC"), ("daily", "* * * * *", "UTC"), ("daily", None, "Moon/Base")],
)
def test_schedule_validation_rejects_ambiguous_or_invalid_input(schedule_type, expression, timezone_name):
    with pytest.raises(ValueError):
        validate_schedule(schedule_type, expression, timezone_name)


def test_durable_task_idempotency_is_enforced_by_database_contract():
    constraints = {constraint.name for constraint in DurableTask.__table__.constraints}
    assert "uq_durable_task_owner_key" in constraints


def test_durable_task_routes_and_recovery_jobs_are_registered():
    paths = {route.path for route in app.routes}
    assert "/api/tasks" in paths
    assert "/api/tasks/items/{task_id}" in paths
    assert "/api/tasks/schedules" in paths
    assert "/api/tasks/approvals/inbox" in paths
    assert "enqueue-due-agent-tasks" in celery_app.conf.beat_schedule
    assert "recover-stale-durable-tasks" in celery_app.conf.beat_schedule


def test_rate_limiter_never_replays_a_request_when_downstream_fails():
    import asyncio

    class RedisStub:
        async def incr(self, _key):
            return 1

        async def expire(self, _key, _seconds):
            return True

    class RequestStub:
        client = type("Client", (), {"host": "127.0.0.1"})()
        url = type("Url", (), {"path": "/api/tasks"})()
        app = type("App", (), {"state": type("State", (), {"redis": RedisStub()})()})()

    async def scenario():
        calls = 0

        async def downstream(_request):
            nonlocal calls
            calls += 1
            raise RuntimeError("after write")

        with pytest.raises(RuntimeError, match="after write"):
            await rate_limit_middleware(RequestStub(), downstream)
        assert calls == 1

    asyncio.run(scenario())
