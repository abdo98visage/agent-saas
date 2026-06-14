"""add hermes runtime layer

Includes profile fields that sync existing agents_md, skills, system_prompt, and soul_md content
into Hermes runtime workspaces. Existing invite_token and is_activated account activation fields remain in earlier
migrations and are intentionally not modified here.

Revision ID: add_hermes_runtime_layer
Revises: add_user_activity_last_seen
Create Date: 2026-06-14
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "add_hermes_runtime_layer"
down_revision = "add_user_activity_last_seen"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("user_api_keys", schema=None) as batch_op:
        batch_op.add_column(sa.Column("owner_type", sa.String(20), nullable=False, server_default="user"))
        batch_op.add_column(sa.Column("profile_id", sa.UUID(), nullable=True))
        batch_op.alter_column("user_id", existing_type=sa.UUID(), nullable=True)
        batch_op.create_index("ix_user_api_keys_owner_type", ["owner_type"])
        batch_op.create_index("ix_user_api_keys_profile_id", ["profile_id"])
        batch_op.create_foreign_key(
            "fk_user_api_keys_profile_id_profiles",
            "profiles",
            ["profile_id"],
            ["id"],
            ondelete="CASCADE",
        )

    with op.batch_alter_table("profiles", schema=None) as batch_op:
        batch_op.add_column(sa.Column("runtime_type", sa.String(50), nullable=False, server_default="hermes"))
        batch_op.add_column(sa.Column("hermes_profile_id", sa.String(100), nullable=True))
        batch_op.add_column(sa.Column("hermes_workspace_path", sa.String(500), nullable=True))
        batch_op.add_column(sa.Column("hermes_sync_status", sa.String(50), nullable=False, server_default="pending"))
        batch_op.add_column(sa.Column("hermes_sync_error", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("version", sa.Integer(), nullable=False, server_default="1"))
        batch_op.add_column(sa.Column("last_synced_at", sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column("provider_key_id", sa.UUID(), nullable=True))
        batch_op.add_column(sa.Column("max_tokens_per_day", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("max_requests_per_day", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("daily_cost_budget", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("allowed_providers", postgresql.JSONB, nullable=False, server_default="[]"))
        batch_op.add_column(sa.Column("allowed_mcp_servers", postgresql.JSONB, nullable=False, server_default="[]"))
        batch_op.add_column(sa.Column("allowed_tools", postgresql.JSONB, nullable=False, server_default="[]"))
        batch_op.add_column(sa.Column("approval_required_tools", postgresql.JSONB, nullable=False, server_default="[]"))
        batch_op.add_column(sa.Column("memory_settings", postgresql.JSONB, nullable=False, server_default="{}"))
        batch_op.create_index("ix_profiles_runtime_type", ["runtime_type"])
        batch_op.create_index("ix_profiles_hermes_profile_id", ["hermes_profile_id"])
        batch_op.create_index("ix_profiles_hermes_sync_status", ["hermes_sync_status"])
        batch_op.create_foreign_key(
            "fk_profiles_provider_key_id_user_api_keys",
            "user_api_keys",
            ["provider_key_id"],
            ["id"],
        )

    with op.batch_alter_table("sessions", schema=None) as batch_op:
        batch_op.add_column(sa.Column("profile_id", sa.UUID(), nullable=True))
        batch_op.add_column(sa.Column("profile_version", sa.Integer(), nullable=True))
        batch_op.create_index("ix_sessions_profile_id", ["profile_id"])
        batch_op.create_foreign_key("fk_sessions_profile_id_profiles", "profiles", ["profile_id"], ["id"])

    op.create_table(
        "agent_runs",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("session_id", sa.UUID(), sa.ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.UUID(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("profile_id", sa.UUID(), sa.ForeignKey("profiles.id"), nullable=True),
        sa.Column("profile_version", sa.Integer(), nullable=True),
        sa.Column("runtime_type", sa.String(50), nullable=False),
        sa.Column("status", sa.String(50), nullable=False, server_default="running"),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("ended_at", sa.DateTime(), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("input_tokens", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("output_tokens", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("total_cost", sa.Float(), nullable=False, server_default="0"),
        sa.Column("model", sa.String(100), nullable=True),
        sa.Column("provider", sa.String(50), nullable=True),
        sa.Column("tools_used", postgresql.JSONB, nullable=False, server_default="[]"),
        sa.Column("mcp_servers_used", postgresql.JSONB, nullable=False, server_default="[]"),
        sa.Column("error_code", sa.String(100), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now()),
    )
    op.create_index("ix_agent_runs_session_id", "agent_runs", ["session_id"])
    op.create_index("ix_agent_runs_user_id", "agent_runs", ["user_id"])
    op.create_index("ix_agent_runs_profile_id", "agent_runs", ["profile_id"])
    op.create_index("ix_agent_runs_runtime_type", "agent_runs", ["runtime_type"])
    op.create_index("ix_agent_runs_status", "agent_runs", ["status"])

    op.create_table(
        "agent_run_events",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("run_id", sa.UUID(), sa.ForeignKey("agent_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("event_type", sa.String(50), nullable=False),
        sa.Column("payload", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now()),
    )
    op.create_index("ix_agent_run_events_run_id", "agent_run_events", ["run_id"])
    op.create_index("ix_agent_run_events_event_type", "agent_run_events", ["event_type"])


def downgrade():
    op.drop_index("ix_agent_run_events_event_type", table_name="agent_run_events")
    op.drop_index("ix_agent_run_events_run_id", table_name="agent_run_events")
    op.drop_table("agent_run_events")
    op.drop_index("ix_agent_runs_status", table_name="agent_runs")
    op.drop_index("ix_agent_runs_runtime_type", table_name="agent_runs")
    op.drop_index("ix_agent_runs_profile_id", table_name="agent_runs")
    op.drop_index("ix_agent_runs_user_id", table_name="agent_runs")
    op.drop_index("ix_agent_runs_session_id", table_name="agent_runs")
    op.drop_table("agent_runs")

    with op.batch_alter_table("sessions", schema=None) as batch_op:
        batch_op.drop_constraint("fk_sessions_profile_id_profiles", type_="foreignkey")
        batch_op.drop_index("ix_sessions_profile_id")
        batch_op.drop_column("profile_version")
        batch_op.drop_column("profile_id")

    with op.batch_alter_table("profiles", schema=None) as batch_op:
        batch_op.drop_constraint("fk_profiles_provider_key_id_user_api_keys", type_="foreignkey")
        batch_op.drop_index("ix_profiles_hermes_sync_status")
        batch_op.drop_index("ix_profiles_hermes_profile_id")
        batch_op.drop_index("ix_profiles_runtime_type")
        batch_op.drop_column("memory_settings")
        batch_op.drop_column("approval_required_tools")
        batch_op.drop_column("allowed_tools")
        batch_op.drop_column("allowed_mcp_servers")
        batch_op.drop_column("allowed_providers")
        batch_op.drop_column("daily_cost_budget")
        batch_op.drop_column("max_requests_per_day")
        batch_op.drop_column("max_tokens_per_day")
        batch_op.drop_column("provider_key_id")
        batch_op.drop_column("last_synced_at")
        batch_op.drop_column("version")
        batch_op.drop_column("hermes_sync_error")
        batch_op.drop_column("hermes_sync_status")
        batch_op.drop_column("hermes_workspace_path")
        batch_op.drop_column("hermes_profile_id")
        batch_op.drop_column("runtime_type")

    with op.batch_alter_table("user_api_keys", schema=None) as batch_op:
        batch_op.drop_constraint("fk_user_api_keys_profile_id_profiles", type_="foreignkey")
        batch_op.drop_index("ix_user_api_keys_profile_id")
        batch_op.drop_index("ix_user_api_keys_owner_type")
        batch_op.alter_column("user_id", existing_type=sa.UUID(), nullable=False)
        batch_op.drop_column("profile_id")
        batch_op.drop_column("owner_type")
