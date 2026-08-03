from datetime import datetime
from uuid import UUID

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin


class DurableTask(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "durable_tasks"
    __table_args__ = (UniqueConstraint("owner_user_id", "idempotency_key", name="uq_durable_task_owner_key"),)

    owner_user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    profile_id: Mapped[UUID | None] = mapped_column(ForeignKey("profiles.id", ondelete="SET NULL"), index=True)
    schedule_id: Mapped[UUID | None] = mapped_column(ForeignKey("task_schedules.id", ondelete="SET NULL"), index=True)
    session_id: Mapped[UUID | None] = mapped_column(ForeignKey("sessions.id", ondelete="SET NULL"), index=True)
    title: Mapped[str] = mapped_column(String(255))
    prompt: Mapped[str] = mapped_column(Text)
    project_context: Mapped[str | None] = mapped_column(Text)
    agent_template_name: Mapped[str] = mapped_column(String(50), default="default")
    profile_name: Mapped[str | None] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(32), default="draft", index=True)
    idempotency_key: Mapped[str] = mapped_column(String(255))
    trace_id: Mapped[str] = mapped_column(String(64), index=True)
    attempt: Mapped[int] = mapped_column(Integer, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, default=3)
    scheduled_for: Mapped[datetime | None] = mapped_column(DateTime, index=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime)
    heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime)
    lease_owner: Mapped[str | None] = mapped_column(String(255), index=True)
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime, index=True)
    cancel_requested: Mapped[bool] = mapped_column(Boolean, default=False)
    checkpoint: Mapped[dict] = mapped_column(JSONB, default=dict)
    result: Mapped[dict] = mapped_column(JSONB, default=dict)
    error_code: Mapped[str | None] = mapped_column(String(100))
    error_message: Mapped[str | None] = mapped_column(Text)

    events: Mapped[list["DurableTaskEvent"]] = relationship(
        back_populates="task", cascade="all, delete-orphan"
    )
    approvals: Mapped[list["ApprovalRequest"]] = relationship(
        back_populates="task", cascade="all, delete-orphan"
    )


class DurableTaskEvent(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "durable_task_events"

    task_id: Mapped[UUID] = mapped_column(ForeignKey("durable_tasks.id", ondelete="CASCADE"), index=True)
    event_type: Mapped[str] = mapped_column(String(64), index=True)
    payload: Mapped[dict] = mapped_column(JSONB, default=dict)

    task: Mapped[DurableTask] = relationship(back_populates="events")


class TaskSchedule(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "task_schedules"

    owner_user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    profile_id: Mapped[UUID | None] = mapped_column(ForeignKey("profiles.id", ondelete="SET NULL"), index=True)
    title: Mapped[str] = mapped_column(String(255))
    prompt: Mapped[str] = mapped_column(Text)
    project_context: Mapped[str | None] = mapped_column(Text)
    agent_template_name: Mapped[str] = mapped_column(String(50), default="default")
    profile_name: Mapped[str | None] = mapped_column(String(100))
    schedule_type: Mapped[str] = mapped_column(String(20))
    cron_expression: Mapped[str | None] = mapped_column(String(100))
    timezone: Mapped[str] = mapped_column(String(64), default="Asia/Riyadh")
    misfire_policy: Mapped[str] = mapped_column(String(20), default="run_once")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    next_run_at: Mapped[datetime | None] = mapped_column(DateTime, index=True)
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime)


class ApprovalRequest(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "approval_requests"
    __table_args__ = (UniqueConstraint("runtime_run_id", "runtime_approval_id", name="uq_runtime_approval"),)

    task_id: Mapped[UUID | None] = mapped_column(ForeignKey("durable_tasks.id", ondelete="CASCADE"), index=True)
    owner_user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    runtime_run_id: Mapped[str] = mapped_column(String(64), index=True)
    runtime_approval_id: Mapped[str] = mapped_column(String(64))
    kind: Mapped[str] = mapped_column(String(32), default="mcp_tool")
    server: Mapped[str | None] = mapped_column(String(100))
    tool: Mapped[str | None] = mapped_column(String(150))
    description: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    decision: Mapped[str | None] = mapped_column(String(20))
    decided_by_user_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    decided_at: Mapped[datetime | None] = mapped_column(DateTime)
    expires_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    request_metadata: Mapped[dict] = mapped_column(JSONB, default=dict)

    task: Mapped[DurableTask | None] = relationship(back_populates="approvals")
