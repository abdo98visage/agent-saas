from datetime import datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.celery_app import celery_app
from app.main import app
from app.main import _authenticated_rate_subject, rate_limit_middleware
from app.core.security import create_access_token
from app.models.durable_task import DurableTask
from app.schemas.durable_task import TaskScheduleUpdate
from app.services.durable_task_service import (
    ACTIVE_TASK_STATES,
    TERMINAL_TASK_STATES,
    next_schedule_run,
    recover_stale_tasks,
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
        headers = {}
        cookies = {}
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


def test_authenticated_rate_limit_subject_is_per_user_behind_shared_nat():
    class RequestStub:
        cookies = {}
        headers = {"Authorization": f"Bearer {create_access_token('employee-a')}"}

    assert _authenticated_rate_subject(RequestStub(), "10.0.0.1") == "user:employee-a"


def test_schedule_update_refreshes_server_generated_timestamps(monkeypatch):
    import asyncio
    import app.api.durable_tasks as durable_tasks_api

    schedule = SimpleNamespace(
        id=uuid4(),
        schedule_type="hourly",
        cron_expression=None,
        timezone="UTC",
        enabled=True,
    )
    user = SimpleNamespace(id=uuid4(), role="admin")

    class DbStub:
        refreshed = False

        async def flush(self):
            return None

        async def refresh(self, item):
            assert item is schedule
            self.refreshed = True

    db = DbStub()

    async def owned_schedule(*_args):
        return schedule

    async def audit(*_args, **_kwargs):
        return None

    monkeypatch.setattr(durable_tasks_api, "_owned_schedule", owned_schedule)
    monkeypatch.setattr(durable_tasks_api, "log_audit_event", audit)
    monkeypatch.setattr(durable_tasks_api, "validate_schedule", lambda *_args: None)
    monkeypatch.setattr(durable_tasks_api, "schedule_response", lambda _item: {"refreshed": db.refreshed})

    result = asyncio.run(durable_tasks_api.update_schedule(
        schedule.id,
        TaskScheduleUpdate(enabled=False),
        db,
        user,
    ))

    assert result == {"refreshed": True}
    assert schedule.enabled is False
    assert schedule.next_run_at is None


def test_recovery_expires_orphaned_pending_approvals(monkeypatch):
    import asyncio
    import app.services.durable_task_service as service

    executed = []

    class Scalars:
        def __init__(self, values):
            self.values = values

        def all(self):
            return self.values

    class Result:
        def __init__(self, values):
            self.values = values

        def scalars(self):
            return Scalars(self.values)

    class Db:
        async def execute(self, statement):
            executed.append(statement)
            return Result([uuid4()] if len(executed) == 1 else [])

    class Transaction:
        async def __aenter__(self):
            return Db()

        async def __aexit__(self, *_args):
            return False

    class Sessions:
        def begin(self):
            return Transaction()

    monkeypatch.setattr(service, "async_session", Sessions())
    result = asyncio.run(recover_stale_tasks(datetime.utcnow() + timedelta(hours=1)))

    assert result == {
        "recovered": 0,
        "failed": 0,
        "expired_approvals": 1,
        "task_ids": [],
    }
    assert len(executed) == 2


def test_rate_limiter_does_not_merge_authenticated_users_behind_shared_nat(monkeypatch):
    import asyncio
    import app.main as main_module

    class RedisStub:
        def __init__(self):
            self.counts = {}

        async def incr(self, key):
            self.counts[key] = self.counts.get(key, 0) + 1
            return self.counts[key]

        async def expire(self, _key, _seconds):
            return True

    class RequestStub:
        client = type("Client", (), {"host": "10.0.0.1"})()
        url = type("Url", (), {"path": "/api/knowledge/search"})()
        cookies = {}

        def __init__(self, user_id, redis):
            self.headers = {"Authorization": f"Bearer {create_access_token(user_id)}"}
            self.app = type("App", (), {"state": type("State", (), {"redis": redis})()})()

    async def scenario():
        redis = RedisStub()

        async def downstream(_request):
            return "ok"

        assert await rate_limit_middleware(RequestStub("employee-a", redis), downstream) == "ok"
        assert await rate_limit_middleware(RequestStub("employee-b", redis), downstream) == "ok"
        blocked = await rate_limit_middleware(RequestStub("employee-a", redis), downstream)
        assert blocked.status_code == 429

    monkeypatch.setattr(main_module, "_RATE_LIMIT", 1)
    asyncio.run(scenario())
