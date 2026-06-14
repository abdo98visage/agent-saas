"""initial_schema

Revision ID: 64336bb416f8
Revises: 
Create Date: 2026-06-11

Full schema with all tables including profiles, assignments, API keys.
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID


revision: str = "64336bb416f8"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # users
    op.create_table(
        "users",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("email", sa.String(255), unique=True, nullable=False, index=True),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("full_name", sa.String(100), nullable=True),
        sa.Column("department", sa.String(50), nullable=True, index=True),
        sa.Column("role", sa.String(20), server_default="employee", index=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), index=True),
        sa.Column("max_tokens_per_day", sa.Integer(), server_default="50000"),
        sa.Column("max_requests_per_day", sa.Integer(), server_default="200"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
    )

    # sessions
    op.create_table(
        "sessions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False, index=True),
        sa.Column("title", sa.String(255), nullable=True),
        sa.Column("agent_template_name", sa.String(50), nullable=True, index=True),
        sa.Column("last_activity", sa.String(50), nullable=True),
        sa.Column("profile_name", sa.String(100), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
    )

    # messages
    op.create_table(
        "messages",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("session_id", UUID(as_uuid=True), sa.ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("project_context", sa.Text(), nullable=True),
        sa.Column("tokens_used", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
    )

    # agent_templates
    op.create_table(
        "agent_templates",
        sa.Column("name", sa.String(50), primary_key=True),
        sa.Column("department", sa.String(50), nullable=True),
        sa.Column("system_prompt", sa.Text(), nullable=False),
        sa.Column("tools", JSONB, server_default="[]"),
        sa.Column("model_name", sa.String(50), server_default="qwen3-14b"),
        sa.Column("max_tokens_per_request", sa.Integer(), server_default="4000"),
        sa.Column("temperature", sa.Float(), server_default="0.7"),
    )

    # telegram_bindings
    op.create_table(
        "telegram_bindings",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False),
        sa.Column("telegram_chat_id", sa.BigInteger(), unique=True, nullable=False, index=True),
        sa.Column("binding_token", sa.String(64), nullable=False, index=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
    )

    # audit_log
    op.create_table(
        "audit_log",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True, index=True),
        sa.Column("action", sa.String(100), nullable=False),
        sa.Column("details", JSONB, server_default="{}"),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
    )

    # kpis
    op.create_table(
        "kpis",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False, index=True),
        sa.Column("date", sa.String(10), nullable=False, index=True),
        sa.Column("tasks_completed", sa.Integer(), server_default="0"),
        sa.Column("messages_sent", sa.Integer(), server_default="0"),
        sa.Column("avg_response_quality", sa.Float(), nullable=True),
        sa.Column("active_minutes", sa.Integer(), server_default="0"),
        sa.Column("tools_used", JSONB, server_default="[]"),
    )

    # profiles (NEW)
    op.create_table(
        "profiles",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("name", sa.String(100), unique=True, nullable=False, index=True),
        sa.Column("slug", sa.String(50), unique=True, nullable=False, index=True),
        sa.Column("description", sa.String(500), nullable=True),
        sa.Column("agents_md", sa.Text(), server_default=""),
        sa.Column("skills", JSONB, server_default="[]"),
        sa.Column("system_prompt", sa.Text(), server_default=""),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), index=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
    )

    # profile_users (NEW)
    op.create_table(
        "profile_users",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("profile_id", UUID(as_uuid=True), sa.ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("priority", sa.Integer(), server_default="0"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
        sa.UniqueConstraint("user_id", "profile_id", name="uq_profile_user_user_profile"),
    )

    # user_api_keys (NEW)
    op.create_table(
        "user_api_keys",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("provider", sa.String(50), server_default="minimax"),
        sa.Column("encrypted_key", sa.Text(), nullable=False),
        sa.Column("key_prefix", sa.String(10), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true")),
        sa.Column("daily_budget", sa.Integer(), server_default="50000"),
        sa.Column("spent_today", sa.Integer(), server_default="0"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("user_api_keys")
    op.drop_table("profile_users")
    op.drop_table("profiles")
    op.drop_table("kpis")
    op.drop_table("audit_log")
    op.drop_table("telegram_bindings")
    op.drop_table("agent_templates")
    op.drop_table("messages")
    op.drop_table("sessions")
    op.drop_table("users")
