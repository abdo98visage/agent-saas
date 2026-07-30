"""add profile runtime toolsets

Revision ID: add_profile_runtime_toolsets
Revises: add_account_lockout
Create Date: 2026-07-23
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "add_profile_runtime_toolsets"
down_revision = "add_account_lockout"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "profiles",
        sa.Column(
            "runtime_toolsets",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[\"skills\", \"vision\", \"clarify\", \"todo\"]'::jsonb"),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("profiles", "runtime_toolsets")
