"""add provider pricing and agent run pricing snapshots

Revision ID: add_provider_pricing_and_run_snapshot
Revises: add_hermes_runtime_layer
Create Date: 2026-06-21
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "add_provider_pricing_and_run_snapshot"
down_revision = "add_hermes_runtime_layer"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "provider_pricing",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("provider", sa.String(50), nullable=False),
        sa.Column("currency", sa.String(8), nullable=False, server_default="USD"),
        sa.Column("monthly_price_usd", sa.Float(), nullable=False, server_default="0"),
        sa.Column("monthly_token_allowance", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now()),
    )
    op.create_index("ix_provider_pricing_provider", "provider_pricing", ["provider"])
    op.create_index("ix_provider_pricing_is_active", "provider_pricing", ["is_active"])

    with op.batch_alter_table("agent_runs", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("pricing_snapshot", postgresql.JSONB, nullable=False, server_default="{}")
        )


def downgrade():
    with op.batch_alter_table("agent_runs", schema=None) as batch_op:
        batch_op.drop_column("pricing_snapshot")

    op.drop_index("ix_provider_pricing_is_active", table_name="provider_pricing")
    op.drop_index("ix_provider_pricing_provider", table_name="provider_pricing")
    op.drop_table("provider_pricing")
