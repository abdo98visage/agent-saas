from datetime import datetime
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_user
from app.core.db import get_db
from app.models.durable_task import ApprovalRequest, DurableTask, DurableTaskEvent, TaskSchedule
from app.models.user import User
from app.schemas.durable_task import (
    ApprovalDecision,
    DurableTaskCreate,
    TaskScheduleCreate,
    TaskScheduleUpdate,
    approval_response,
    durable_task_response,
    schedule_response,
)
from app.services.agent_service import AgentService
from app.services.durable_task_service import next_schedule_run, utcnow, validate_schedule
from app.services.audit_service import log_audit_event
from app.tasks import run_durable_agent_task


router = APIRouter()
agent_service = AgentService()


def _can_access(user: User, owner_user_id: UUID) -> bool:
    return user.role == "admin" or user.id == owner_user_id


async def _owned_task(db: AsyncSession, task_id: UUID, user: User) -> DurableTask:
    task = await db.get(DurableTask, task_id)
    if not task or not _can_access(user, task.owner_user_id):
        raise HTTPException(status_code=404, detail="Task not found")
    return task


async def _owned_schedule(db: AsyncSession, schedule_id: UUID, user: User) -> TaskSchedule:
    schedule = await db.get(TaskSchedule, schedule_id)
    if not schedule or not _can_access(user, schedule.owner_user_id):
        raise HTTPException(status_code=404, detail="Schedule not found")
    return schedule


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_task(
    request: DurableTaskCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    existing_result = await db.execute(
        select(DurableTask).where(
            DurableTask.owner_user_id == user.id,
            DurableTask.idempotency_key == request.idempotency_key,
        )
    )
    existing = existing_result.scalar_one_or_none()
    if existing:
        if existing.prompt != request.prompt or existing.profile_name != request.profile_name:
            raise HTTPException(status_code=409, detail="Idempotency key was already used for another task")
        return durable_task_response(existing)

    try:
        profile = await agent_service.resolve_user_profile(db, user.id, profile_name=request.profile_name)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid task profile") from exc
    task = DurableTask(
        owner_user_id=user.id,
        profile_id=profile.id if profile else None,
        title=request.title,
        prompt=request.prompt,
        project_context=request.project_context,
        agent_template_name=request.agent_template_name,
        profile_name=request.profile_name,
        status="queued" if request.start_immediately else "draft",
        idempotency_key=request.idempotency_key,
        trace_id=uuid4().hex,
        max_attempts=request.max_attempts,
        scheduled_for=utcnow() if request.start_immediately else None,
    )
    db.add(task)
    await db.flush()
    db.add(DurableTaskEvent(
        task_id=task.id,
        event_type="queued" if request.start_immediately else "drafted",
        payload={"trace_id": task.trace_id},
    ))
    await log_audit_event(
        db, user.id, "task_created", {"status": task.status},
        event_category="task", subject_type="durable_task", subject_id=str(task.id), task_id=task.id,
    )
    await db.commit()
    if request.start_immediately:
        run_durable_agent_task.delay(str(task.id))
    return durable_task_response(task)


@router.get("")
async def list_tasks(
    task_status: str | None = Query(default=None, alias="status"),
    limit: int = Query(default=50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    query = select(DurableTask).order_by(DurableTask.created_at.desc()).limit(limit)
    if user.role != "admin":
        query = query.where(DurableTask.owner_user_id == user.id)
    if task_status:
        query = query.where(DurableTask.status == task_status)
    result = await db.execute(query)
    tasks = result.scalars().all()
    return {"tasks": [durable_task_response(task) for task in tasks], "count": len(tasks)}


@router.get("/items/{task_id}")
async def get_task(
    task_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    task = await _owned_task(db, task_id, user)
    events_result = await db.execute(
        select(DurableTaskEvent)
        .where(DurableTaskEvent.task_id == task.id)
        .order_by(DurableTaskEvent.created_at.asc())
    )
    response = durable_task_response(task)
    response["events"] = [
        {"id": str(event.id), "type": event.event_type, "payload": event.payload, "created_at": event.created_at}
        for event in events_result.scalars().all()
    ]
    return response


@router.post("/items/{task_id}/start")
async def start_task(
    task_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    task = await _owned_task(db, task_id, user)
    if task.status != "draft":
        raise HTTPException(status_code=409, detail="Only draft tasks can be started")
    task.status = "queued"
    task.scheduled_for = utcnow()
    db.add(DurableTaskEvent(task_id=task.id, event_type="queued", payload={}))
    await log_audit_event(db, user.id, "task_started", event_category="task", subject_type="durable_task", subject_id=str(task.id), task_id=task.id)
    await db.flush()
    await db.refresh(task)
    response = durable_task_response(task)
    await db.commit()
    run_durable_agent_task.delay(str(task.id))
    return response


@router.post("/items/{task_id}/cancel")
async def cancel_task(
    task_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    task = await _owned_task(db, task_id, user)
    if task.status in {"succeeded", "failed", "cancelled", "expired"}:
        raise HTTPException(status_code=409, detail="Task is already terminal")
    task.cancel_requested = True
    if task.status in {"draft", "queued", "paused"}:
        task.status = "cancelled"
        task.finished_at = utcnow()
    db.add(DurableTaskEvent(task_id=task.id, event_type="cancel_requested", payload={}))
    await log_audit_event(db, user.id, "task_cancel_requested", event_category="task", subject_type="durable_task", subject_id=str(task.id), task_id=task.id)
    await db.flush()
    await db.refresh(task)
    response = durable_task_response(task)
    await db.commit()
    return response


@router.post("/items/{task_id}/retry")
async def retry_task(
    task_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    task = await _owned_task(db, task_id, user)
    if task.status not in {"failed", "cancelled"}:
        raise HTTPException(status_code=409, detail="Only failed or cancelled tasks can be retried")
    if (task.checkpoint or {}).get("side_effect_started"):
        raise HTTPException(status_code=409, detail="Task cannot be retried safely after an external action")
    task.status = "queued"
    task.cancel_requested = False
    task.finished_at = None
    task.error_code = None
    task.error_message = None
    db.add(DurableTaskEvent(task_id=task.id, event_type="retry_requested", payload={"attempt": task.attempt}))
    await log_audit_event(db, user.id, "task_retry_requested", {"attempt": task.attempt}, event_category="task", subject_type="durable_task", subject_id=str(task.id), task_id=task.id)
    await db.flush()
    await db.refresh(task)
    response = durable_task_response(task)
    await db.commit()
    run_durable_agent_task.delay(str(task.id))
    return response


@router.post("/schedules", status_code=status.HTTP_201_CREATED)
async def create_schedule(
    request: TaskScheduleCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    try:
        validate_schedule(request.schedule_type, request.cron_expression, request.timezone)
        profile = await agent_service.resolve_user_profile(db, user.id, profile_name=request.profile_name)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    schedule = TaskSchedule(
        owner_user_id=user.id,
        profile_id=profile.id if profile else None,
        **request.model_dump(),
        next_run_at=next_schedule_run(
            request.schedule_type, request.cron_expression, request.timezone
        ) if request.enabled else None,
    )
    db.add(schedule)
    await db.flush()
    await log_audit_event(db, user.id, "schedule_created", {"schedule_type": schedule.schedule_type}, event_category="task", subject_type="task_schedule", subject_id=str(schedule.id))
    return schedule_response(schedule)


@router.get("/schedules")
async def list_schedules(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    query = select(TaskSchedule).order_by(TaskSchedule.created_at.desc())
    if user.role != "admin":
        query = query.where(TaskSchedule.owner_user_id == user.id)
    result = await db.execute(query)
    schedules = result.scalars().all()
    return {"schedules": [schedule_response(item) for item in schedules], "count": len(schedules)}


@router.put("/schedules/{schedule_id}")
async def update_schedule(
    schedule_id: UUID,
    request: TaskScheduleUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    schedule = await _owned_schedule(db, schedule_id, user)
    values = request.model_dump(exclude_unset=True)
    for key, value in values.items():
        setattr(schedule, key, value)
    try:
        validate_schedule(schedule.schedule_type, schedule.cron_expression, schedule.timezone)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    schedule.next_run_at = next_schedule_run(
        schedule.schedule_type, schedule.cron_expression, schedule.timezone
    ) if schedule.enabled else None
    await db.flush()
    await log_audit_event(db, user.id, "schedule_updated", {"enabled": schedule.enabled}, event_category="task", subject_type="task_schedule", subject_id=str(schedule.id))
    return schedule_response(schedule)


@router.delete("/schedules/{schedule_id}")
async def delete_schedule(
    schedule_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    schedule = await _owned_schedule(db, schedule_id, user)
    await log_audit_event(db, user.id, "schedule_deleted", event_category="task", subject_type="task_schedule", subject_id=str(schedule.id))
    await db.delete(schedule)
    return {"status": "deleted", "id": str(schedule_id)}


@router.get("/approvals/inbox")
async def approval_inbox(
    approval_status: str = Query(default="pending", alias="status"),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    query = select(ApprovalRequest).where(ApprovalRequest.status == approval_status)
    if user.role != "admin":
        query = query.where(ApprovalRequest.owner_user_id == user.id)
    result = await db.execute(query.order_by(ApprovalRequest.created_at.desc()))
    approvals = result.scalars().all()
    return {"approvals": [approval_response(item) for item in approvals], "count": len(approvals)}


@router.post("/approvals/{approval_id}/decision")
async def decide_approval(
    approval_id: UUID,
    request: ApprovalDecision,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    approval = await db.get(ApprovalRequest, approval_id)
    if not approval or not _can_access(user, approval.owner_user_id):
        raise HTTPException(status_code=404, detail="Approval not found")
    if approval.status != "pending":
        raise HTTPException(status_code=409, detail="Approval is no longer pending")
    if approval.expires_at <= datetime.utcnow():
        approval.status = "expired"
        raise HTTPException(status_code=410, detail="Approval expired")
    approval.status = "decided"
    approval.decision = request.decision
    approval.decided_by_user_id = user.id
    approval.decided_at = datetime.utcnow()
    await db.flush()
    await log_audit_event(
        db, user.id, "approval_decided", {"decision": request.decision, "tool": approval.tool, "server": approval.server},
        event_category="approval", subject_type="approval_request", subject_id=str(approval.id), task_id=approval.task_id,
    )
    return approval_response(approval)
