"""add evaluation datasets, regression runs, and content-free feedback

Revision ID: evaluation_gates
Revises: tamper_evident_audit
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "evaluation_gates"
down_revision = "tamper_evident_audit"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "evaluation_suites",
        sa.Column("name", sa.String(150), nullable=False),
        sa.Column("profile_id", sa.UUID(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("cases", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("thresholds", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("baseline_run_id", sa.UUID(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["profile_id"], ["profiles.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_evaluation_suites_profile_id", "evaluation_suites", ["profile_id"])
    op.create_index("ix_evaluation_suites_is_active", "evaluation_suites", ["is_active"])

    op.create_table(
        "evaluation_runs",
        sa.Column("suite_id", sa.UUID(), nullable=False),
        sa.Column("profile_id", sa.UUID(), nullable=True),
        sa.Column("profile_version", sa.Integer(), nullable=True),
        sa.Column("triggered_by_user_id", sa.UUID(), nullable=True),
        sa.Column("status", sa.String(24), nullable=False, server_default="running"),
        sa.Column("candidate_label", sa.String(100), nullable=True),
        sa.Column("metrics", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("case_results", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("started_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("is_baseline", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["suite_id"], ["evaluation_suites.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["profile_id"], ["profiles.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["triggered_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in ("suite_id", "profile_id", "profile_version", "status", "is_baseline"):
        op.create_index(f"ix_evaluation_runs_{column}", "evaluation_runs", [column])

    op.create_table(
        "agent_feedback",
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("agent_run_id", sa.UUID(), nullable=False),
        sa.Column("rating", sa.Integer(), nullable=False),
        sa.Column("outcome", sa.String(20), nullable=False),
        sa.Column("tags", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("note_hash", sa.String(64), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["agent_run_id"], ["agent_runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "agent_run_id", name="uq_agent_feedback_user_run"),
    )
    op.create_index("ix_agent_feedback_user_id", "agent_feedback", ["user_id"])
    op.create_index("ix_agent_feedback_agent_run_id", "agent_feedback", ["agent_run_id"])
    op.create_index("ix_agent_feedback_outcome", "agent_feedback", ["outcome"])


def downgrade() -> None:
    op.drop_table("agent_feedback")
    op.drop_table("evaluation_runs")
    op.drop_table("evaluation_suites")
