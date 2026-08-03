import asyncio
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from croniter import croniter
from sqlalchemy import select

from app.core.config import settings
from app.core.db import async_session
from app.models.durable_task import ApprovalRequest, DurableTask, DurableTaskEvent, TaskSchedule
from app.models.session import Session
from app.models.user import User
from app.services.agent_service import AgentService
from app.services.hermes_orchestrator import hermes_orchestrator
from app.services.token_tracker import check_token_quota, reserve_request_quota


TERMINAL_TASK_STATES = {"succeeded", "failed", "cancelled", "expired"}
ACTIVE_TASK_STATES = {"queued", "running", "waiting_approval", "paused"}


def utcnow() -> datetime:
    return datetime.utcnow()


def validate_schedule(schedule_type: str, expression: str | None, timezone_name: str) -> None:
    try:
        ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError as exc:
        raise ValueError("Unknown schedule timezone") from exc
    if schedule_type == "cron":
        if not expression or not croniter.is_valid(expression):
            raise ValueError("A valid cron expression is required")
    elif expression:
        raise ValueError("cron_expression is only valid for cron schedules")


def next_schedule_run(
    schedule_type: str,
    expression: str | None,
    timezone_name: str,
    after_utc: datetime | None = None,
) -> datetime:
    validate_schedule(schedule_type, expression, timezone_name)
    after = (after_utc or utcnow()).replace(tzinfo=timezone.utc)
    local = after.astimezone(ZoneInfo(timezone_name))
    expressions = {
        "hourly": "0 * * * *",
        "daily": "0 8 * * *",
        "weekly": "0 8 * * 1",
    }
    value = croniter(expression or expressions[schedule_type], local).get_next(datetime)
    if value.tzinfo is None:
        value = value.replace(tzinfo=ZoneInfo(timezone_name))
    return value.astimezone(timezone.utc).replace(tzinfo=None)


async def append_task_event(task_id: UUID, event_type: str, payload: dict | None = None) -> None:
    async with async_session.begin() as db:
        db.add(DurableTaskEvent(task_id=task_id, event_type=event_type, payload=payload or {}))


async def acquire_task(task_id: UUID, lease_owner: str) -> DurableTask | None:
    now = utcnow()
    async with async_session.begin() as db:
        result = await db.execute(
            select(DurableTask).where(DurableTask.id == task_id).with_for_update()
        )
        task = result.scalar_one_or_none()
        if not task or task.status in TERMINAL_TASK_STATES:
            return None
        if task.cancel_requested:
            task.status = "cancelled"
            task.finished_at = now
            return None
        if task.status == "running" and task.lease_expires_at and task.lease_expires_at > now:
            return None
        if task.status not in {"queued", "running"}:
            return None
        task.status = "running"
        task.started_at = task.started_at or now
        task.heartbeat_at = now
        task.lease_owner = lease_owner
        task.lease_expires_at = now + timedelta(seconds=settings.durable_task_lease_seconds)
        task.attempt = int(task.attempt or 0) + 1
        task.error_code = None
        task.error_message = None
        await db.flush()
        return task


async def heartbeat_task(task_id: UUID, lease_owner: str, checkpoint: dict | None = None) -> bool:
    now = utcnow()
    async with async_session.begin() as db:
        task = await db.get(DurableTask, task_id)
        if not task or task.lease_owner != lease_owner or task.cancel_requested:
            return False
        task.heartbeat_at = now
        task.lease_expires_at = now + timedelta(seconds=settings.durable_task_lease_seconds)
        if checkpoint is not None:
            task.checkpoint = checkpoint
        return True


async def _set_task_state(task_id: UUID, status: str, **values) -> None:
    async with async_session.begin() as db:
        task = await db.get(DurableTask, task_id)
        if not task:
            return
        task.status = status
        for key, value in values.items():
            setattr(task, key, value)


async def _persist_approval(task: DurableTask, event: dict) -> ApprovalRequest:
    now = utcnow()
    async with async_session.begin() as db:
        result = await db.execute(
            select(ApprovalRequest).where(
                ApprovalRequest.runtime_run_id == str(event.get("run_id") or ""),
                ApprovalRequest.runtime_approval_id == str(event.get("approval_id") or ""),
            )
        )
        approval = result.scalar_one_or_none()
        if approval:
            return approval
        approval = ApprovalRequest(
            task_id=task.id,
            owner_user_id=task.owner_user_id,
            runtime_run_id=str(event.get("run_id") or ""),
            runtime_approval_id=str(event.get("approval_id") or ""),
            server=str(event.get("server") or "") or None,
            tool=str(event.get("tool") or "") or None,
            description=str(event.get("description") or "")[:2000] or None,
            status="pending",
            expires_at=now + timedelta(minutes=settings.durable_task_approval_timeout_minutes),
            request_metadata={"choices": event.get("choices") or ["approve", "deny"]},
        )
        db.add(approval)
        await db.flush()
        return approval


async def wait_for_approval(task: DurableTask, event: dict, lease_owner: str) -> str:
    approval = await _persist_approval(task, event)
    await _set_task_state(task.id, "waiting_approval")
    await append_task_event(task.id, "approval_requested", {"approval_id": str(approval.id)})
    while utcnow() < approval.expires_at:
        await asyncio.sleep(1)
        if not await heartbeat_task(task.id, lease_owner):
            return "deny"
        async with async_session() as db:
            current = await db.get(ApprovalRequest, approval.id)
            if current and current.status == "decided" and current.decision in {"approve", "deny"}:
                await hermes_orchestrator.respond_approval(
                    current.runtime_run_id,
                    current.runtime_approval_id,
                    current.decision,
                )
                await _set_task_state(task.id, "running")
                await append_task_event(task.id, "approval_applied", {"decision": current.decision})
                return current.decision
    async with async_session.begin() as db:
        current = await db.get(ApprovalRequest, approval.id)
        if current and current.status == "pending":
            current.status = "expired"
            current.decision = "deny"
            current.decided_at = utcnow()
    await hermes_orchestrator.respond_approval(
        approval.runtime_run_id, approval.runtime_approval_id, "deny"
    )
    raise TimeoutError("Approval request expired")


async def execute_durable_task(task_id: UUID, lease_owner: str) -> dict:
    task = await acquire_task(task_id, lease_owner)
    if not task:
        return {"status": "not_acquired"}
    await append_task_event(task.id, "started", {"attempt": task.attempt, "trace_id": task.trace_id})
    checkpoint = dict(task.checkpoint or {})
    response_text = ""
    done: dict = {}
    try:
        async with async_session.begin() as quota_db:
            user = await quota_db.get(User, task.owner_user_id)
            if not user or not user.is_active or not user.is_activated:
                raise PermissionError("Task owner is unavailable")
            if not await reserve_request_quota(quota_db, str(user.id), user.max_requests_per_day):
                raise RuntimeError("Daily request quota exceeded")
            if not await check_token_quota(quota_db, str(user.id), user.max_tokens_per_day):
                raise RuntimeError("Daily token quota exceeded")

        if not task.session_id:
            async with async_session.begin() as session_db:
                session_obj = Session(
                    id=uuid4(),
                    user_id=task.owner_user_id,
                    title=task.title,
                    agent_template_name=task.agent_template_name,
                    profile_name=task.profile_name,
                )
                session_db.add(session_obj)
                await session_db.flush()
                task.session_id = session_obj.id
            await _set_task_state(task.id, "running", session_id=task.session_id)

        service = AgentService()
        async with async_session.begin() as agent_db:
            stream = service.run_agent_stream(
                db=agent_db,
                user_id=str(task.owner_user_id),
                conversation_id=str(task.session_id),
                user_message=task.prompt,
                agent_template_name=task.agent_template_name,
                project_context=task.project_context,
                profile_name=task.profile_name,
            )
            async for event in stream:
                event_type = str(event.get("type") or "event")
                if event_type == "chunk":
                    response_text += str(event.get("content") or "")
                elif event_type == "done":
                    done = dict(event)
                elif event_type == "mcp_tool_started":
                    checkpoint["last_tool"] = {
                        "server": event.get("server"), "tool": event.get("tool"), "call_id": event.get("call_id")
                    }
                elif event_type == "mcp_approval_required":
                    if await wait_for_approval(task, event, lease_owner) == "approve":
                        checkpoint["side_effect_started"] = True
                        checkpoint["approved_tool"] = {
                            "server": event.get("server"), "tool": event.get("tool")
                        }
                checkpoint["last_event"] = event_type
                checkpoint["response_chars"] = len(response_text)
                if not await heartbeat_task(task.id, lease_owner, checkpoint):
                    await stream.aclose()
                    raise asyncio.CancelledError("Task cancellation requested")
                await append_task_event(task.id, event_type, {
                    key: value for key, value in event.items() if key not in {"content", "usage"}
                })

        result = {
            "content": response_text,
            "message_id": done.get("message_id"),
            "conversation_id": done.get("conversation_id"),
            "tokens_used": done.get("tokens_used", 0),
            "total_cost": done.get("total_cost", 0.0),
            "model": done.get("model"),
            "provider": done.get("provider"),
        }
        await _set_task_state(
            task.id,
            "succeeded",
            result=result,
            checkpoint={**checkpoint, "completed": True},
            session_id=task.session_id,
            finished_at=utcnow(),
            lease_owner=None,
            lease_expires_at=None,
        )
        await append_task_event(task.id, "succeeded", {"tokens_used": result["tokens_used"]})
        return {"status": "succeeded", "task_id": str(task.id)}
    except asyncio.CancelledError:
        await _set_task_state(
            task.id, "cancelled", finished_at=utcnow(), lease_owner=None, lease_expires_at=None
        )
        await append_task_event(task.id, "cancelled")
        return {"status": "cancelled", "task_id": str(task.id)}
    except Exception as exc:
        safe_to_retry = not checkpoint.get("side_effect_started") and task.attempt < task.max_attempts
        status = "queued" if safe_to_retry else "failed"
        error_code = "UnsafeRetryBlocked" if checkpoint.get("side_effect_started") else exc.__class__.__name__
        await _set_task_state(
            task.id,
            status,
            checkpoint=checkpoint,
            error_code=error_code,
            error_message=str(exc)[:2000],
            finished_at=None if safe_to_retry else utcnow(),
            lease_owner=None,
            lease_expires_at=None,
        )
        await append_task_event(task.id, "retry_queued" if safe_to_retry else "failed", {
            "error_code": error_code, "attempt": task.attempt
        })
        if safe_to_retry:
            from app.tasks import run_durable_agent_task
            run_durable_agent_task.apply_async(args=[str(task.id)], countdown=min(60, 2 ** task.attempt))
        return {"status": status, "task_id": str(task.id), "error_code": error_code}


async def enqueue_due_schedules(now: datetime | None = None) -> list[str]:
    current = now or utcnow()
    created: list[str] = []
    async with async_session.begin() as db:
        result = await db.execute(
            select(TaskSchedule)
            .where(
                TaskSchedule.enabled.is_(True),
                TaskSchedule.next_run_at.is_not(None),
                TaskSchedule.next_run_at <= current,
            )
            .with_for_update(skip_locked=True)
        )
        for schedule in result.scalars().all():
            due_at = schedule.next_run_at
            next_after_due = next_schedule_run(
                schedule.schedule_type, schedule.cron_expression, schedule.timezone, due_at
            )
            is_misfire = due_at < current - timedelta(minutes=2)
            should_run = not is_misfire or schedule.misfire_policy == "run_once"
            if should_run:
                key = f"schedule:{schedule.id}:{due_at.isoformat()}"
                existing = await db.execute(
                    select(DurableTask.id).where(
                        DurableTask.owner_user_id == schedule.owner_user_id,
                        DurableTask.idempotency_key == key,
                    )
                )
                if existing.scalar_one_or_none() is None:
                    task = DurableTask(
                        owner_user_id=schedule.owner_user_id,
                        profile_id=schedule.profile_id,
                        schedule_id=schedule.id,
                        title=schedule.title,
                        prompt=schedule.prompt,
                        project_context=schedule.project_context,
                        agent_template_name=schedule.agent_template_name,
                        profile_name=schedule.profile_name,
                        status="queued",
                        idempotency_key=key,
                        trace_id=uuid4().hex,
                        scheduled_for=due_at,
                    )
                    db.add(task)
                    await db.flush()
                    db.add(DurableTaskEvent(
                        task_id=task.id,
                        event_type="scheduled",
                        payload={"schedule_id": str(schedule.id), "due_at": due_at.isoformat()},
                    ))
                    created.append(str(task.id))
            schedule.last_run_at = due_at if should_run else schedule.last_run_at
            next_run = next_after_due
            while next_run <= current:
                next_run = next_schedule_run(
                    schedule.schedule_type, schedule.cron_expression, schedule.timezone, next_run
                )
            schedule.next_run_at = next_run
    return created


async def recover_stale_tasks(now: datetime | None = None) -> dict:
    current = now or utcnow()
    recovered = 0
    failed = 0
    task_ids: list[str] = []
    async with async_session.begin() as db:
        result = await db.execute(
            select(DurableTask)
            .where(
                DurableTask.status.in_(["running", "waiting_approval"]),
                DurableTask.lease_expires_at.is_not(None),
                DurableTask.lease_expires_at < current,
            )
            .with_for_update(skip_locked=True)
        )
        for task in result.scalars().all():
            if (task.checkpoint or {}).get("side_effect_started") or task.attempt >= task.max_attempts:
                task.status = "failed"
                task.error_code = "UnsafeRetryBlocked" if (task.checkpoint or {}).get("side_effect_started") else "AttemptsExhausted"
                task.error_message = "Worker lease expired and the task cannot be retried safely"
                task.finished_at = current
                failed += 1
            else:
                task.status = "queued"
                task.error_code = "WorkerLeaseExpired"
                task.error_message = "Worker lease expired; task queued for recovery"
                recovered += 1
                task_ids.append(str(task.id))
            task.lease_owner = None
            task.lease_expires_at = None
            db.add(DurableTaskEvent(
                task_id=task.id,
                event_type="recovered" if task.status == "queued" else "failed",
                payload={"reason": task.error_code},
            ))
    return {"recovered": recovered, "failed": failed, "task_ids": task_ids}
