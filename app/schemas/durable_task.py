from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class DurableTaskCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    prompt: str = Field(min_length=1, max_length=100_000)
    project_context: str | None = Field(default=None, max_length=100_000)
    agent_template_name: str = Field(default="default", min_length=1, max_length=50)
    profile_name: str | None = Field(default=None, max_length=100)
    idempotency_key: str = Field(min_length=8, max_length=255)
    start_immediately: bool = True
    max_attempts: int = Field(default=3, ge=1, le=5)

    @field_validator("title", "prompt", "agent_template_name", "idempotency_key")
    @classmethod
    def strip_required(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Value must not be blank")
        return value


class TaskScheduleCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    prompt: str = Field(min_length=1, max_length=100_000)
    project_context: str | None = Field(default=None, max_length=100_000)
    agent_template_name: str = Field(default="default", min_length=1, max_length=50)
    profile_name: str | None = Field(default=None, max_length=100)
    schedule_type: Literal["hourly", "daily", "weekly", "cron"]
    cron_expression: str | None = Field(default=None, max_length=100)
    timezone: str = Field(default="Asia/Riyadh", min_length=1, max_length=64)
    misfire_policy: Literal["skip", "run_once"] = "run_once"
    enabled: bool = True


class TaskScheduleUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    prompt: str | None = Field(default=None, min_length=1, max_length=100_000)
    project_context: str | None = Field(default=None, max_length=100_000)
    agent_template_name: str | None = Field(default=None, min_length=1, max_length=50)
    profile_name: str | None = Field(default=None, max_length=100)
    schedule_type: Literal["hourly", "daily", "weekly", "cron"] | None = None
    cron_expression: str | None = Field(default=None, max_length=100)
    timezone: str | None = Field(default=None, min_length=1, max_length=64)
    misfire_policy: Literal["skip", "run_once"] | None = None
    enabled: bool | None = None


class ApprovalDecision(BaseModel):
    decision: Literal["approve", "deny"]


def durable_task_response(task) -> dict:
    return {
        "id": str(task.id),
        "owner_user_id": str(task.owner_user_id),
        "profile_id": str(task.profile_id) if task.profile_id else None,
        "schedule_id": str(task.schedule_id) if task.schedule_id else None,
        "session_id": str(task.session_id) if task.session_id else None,
        "title": task.title,
        "status": task.status,
        "idempotency_key": task.idempotency_key,
        "trace_id": task.trace_id,
        "attempt": task.attempt,
        "max_attempts": task.max_attempts,
        "scheduled_for": task.scheduled_for,
        "started_at": task.started_at,
        "finished_at": task.finished_at,
        "heartbeat_at": task.heartbeat_at,
        "cancel_requested": task.cancel_requested,
        "checkpoint": task.checkpoint or {},
        "result": task.result or {},
        "error_code": task.error_code,
        "error_message": task.error_message,
        "created_at": task.created_at,
        "updated_at": task.updated_at,
    }


def schedule_response(schedule) -> dict:
    return {
        "id": str(schedule.id),
        "owner_user_id": str(schedule.owner_user_id),
        "profile_id": str(schedule.profile_id) if schedule.profile_id else None,
        "title": schedule.title,
        "schedule_type": schedule.schedule_type,
        "cron_expression": schedule.cron_expression,
        "timezone": schedule.timezone,
        "misfire_policy": schedule.misfire_policy,
        "enabled": schedule.enabled,
        "next_run_at": schedule.next_run_at,
        "last_run_at": schedule.last_run_at,
        "created_at": schedule.created_at,
        "updated_at": schedule.updated_at,
    }


def approval_response(approval) -> dict:
    return {
        "id": str(approval.id),
        "task_id": str(approval.task_id) if approval.task_id else None,
        "owner_user_id": str(approval.owner_user_id),
        "kind": approval.kind,
        "server": approval.server,
        "tool": approval.tool,
        "description": approval.description,
        "status": approval.status,
        "decision": approval.decision,
        "expires_at": approval.expires_at,
        "decided_at": approval.decided_at,
        "created_at": approval.created_at,
    }
