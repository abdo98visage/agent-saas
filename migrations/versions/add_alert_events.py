"""add alert events table

Revision ID: add_alert_events
Revises: add_user_token_version
Create Date: 2026-06-21
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "add_alert_events"
down_revision = "add_user_token_version"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "alert_events",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("alert_type", sa.String(50), nullable=False),
        sa.Column("severity", sa.String(20), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("fingerprint", sa.String(255), nullable=False),
        sa.Column("context", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("first_seen_at", sa.DateTime(), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(), nullable=False),
        sa.Column("last_notified_at", sa.DateTime(), nullable=True),
        sa.Column("is_acknowledged", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now()),
    )
    op.create_index("ix_alert_events_alert_type", "alert_events", ["alert_type"])
    op.create_index("ix_alert_events_severity", "alert_events", ["severity"])
    op.create_index("ix_alert_events_status", "alert_events", ["status"])
    op.create_index("ix_alert_events_fingerprint", "alert_events", ["fingerprint"], unique=True)


def downgrade():
    op.drop_index("ix_alert_events_fingerprint", table_name="alert_events")
    op.drop_index("ix_alert_events_status", table_name="alert_events")
    op.drop_index("ix_alert_events_severity", table_name="alert_events")
    op.drop_index("ix_alert_events_alert_type", table_name="alert_events")
    op.drop_table("alert_events")
