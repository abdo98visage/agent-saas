"""add durable task orchestration

Revision ID: add_durable_tasks
Revises: pending_telegram_bindings
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "add_durable_tasks"
down_revision = "pending_telegram_bindings"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "task_schedules",
        sa.Column("owner_user_id", sa.UUID(), nullable=False),
        sa.Column("profile_id", sa.UUID(), nullable=True),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("prompt", sa.Text(), nullable=False),
        sa.Column("project_context", sa.Text(), nullable=True),
        sa.Column("agent_template_name", sa.String(50), nullable=False, server_default="default"),
        sa.Column("profile_name", sa.String(100), nullable=True),
        sa.Column("schedule_type", sa.String(20), nullable=False),
        sa.Column("cron_expression", sa.String(100), nullable=True),
        sa.Column("timezone", sa.String(64), nullable=False, server_default="Asia/Riyadh"),
        sa.Column("misfire_policy", sa.String(20), nullable=False, server_default="run_once"),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("next_run_at", sa.DateTime(), nullable=True),
        sa.Column("last_run_at", sa.DateTime(), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["owner_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["profile_id"], ["profiles.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in ("owner_user_id", "profile_id", "enabled", "next_run_at"):
        op.create_index(f"ix_task_schedules_{column}", "task_schedules", [column])

    op.create_table(
        "durable_tasks",
        sa.Column("owner_user_id", sa.UUID(), nullable=False),
        sa.Column("profile_id", sa.UUID(), nullable=True),
        sa.Column("schedule_id", sa.UUID(), nullable=True),
        sa.Column("session_id", sa.UUID(), nullable=True),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("prompt", sa.Text(), nullable=False),
        sa.Column("project_context", sa.Text(), nullable=True),
        sa.Column("agent_template_name", sa.String(50), nullable=False, server_default="default"),
        sa.Column("profile_name", sa.String(100), nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="draft"),
        sa.Column("idempotency_key", sa.String(255), nullable=False),
        sa.Column("trace_id", sa.String(64), nullable=False),
        sa.Column("attempt", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("scheduled_for", sa.DateTime(), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.Column("heartbeat_at", sa.DateTime(), nullable=True),
        sa.Column("lease_owner", sa.String(255), nullable=True),
        sa.Column("lease_expires_at", sa.DateTime(), nullable=True),
        sa.Column("cancel_requested", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("checkpoint", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("result", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("error_code", sa.String(100), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["owner_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["profile_id"], ["profiles.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["schedule_id"], ["task_schedules.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["session_id"], ["sessions.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("owner_user_id", "idempotency_key", name="uq_durable_task_owner_key"),
    )
    for column in (
        "owner_user_id", "profile_id", "schedule_id", "session_id", "status", "trace_id",
        "scheduled_for", "lease_owner", "lease_expires_at",
    ):
        op.create_index(f"ix_durable_tasks_{column}", "durable_tasks", [column])

    op.create_table(
        "durable_task_events",
        sa.Column("task_id", sa.UUID(), nullable=False),
        sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["task_id"], ["durable_tasks.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_durable_task_events_task_id", "durable_task_events", ["task_id"])
    op.create_index("ix_durable_task_events_event_type", "durable_task_events", ["event_type"])

    op.create_table(
        "approval_requests",
        sa.Column("task_id", sa.UUID(), nullable=True),
        sa.Column("owner_user_id", sa.UUID(), nullable=False),
        sa.Column("runtime_run_id", sa.String(64), nullable=False),
        sa.Column("runtime_approval_id", sa.String(64), nullable=False),
        sa.Column("kind", sa.String(32), nullable=False, server_default="mcp_tool"),
        sa.Column("server", sa.String(100), nullable=True),
        sa.Column("tool", sa.String(150), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("decision", sa.String(20), nullable=True),
        sa.Column("decided_by_user_id", sa.UUID(), nullable=True),
        sa.Column("decided_at", sa.DateTime(), nullable=True),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("request_metadata", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["task_id"], ["durable_tasks.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["owner_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["decided_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("runtime_run_id", "runtime_approval_id", name="uq_runtime_approval"),
    )
    for column in ("task_id", "owner_user_id", "runtime_run_id", "status", "expires_at"):
        op.create_index(f"ix_approval_requests_{column}", "approval_requests", [column])


def downgrade() -> None:
    op.drop_table("approval_requests")
    op.drop_table("durable_task_events")
    op.drop_table("durable_tasks")
    op.drop_table("task_schedules")
