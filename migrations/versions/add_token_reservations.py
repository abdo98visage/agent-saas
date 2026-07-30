"""add atomic token reservations

Revision ID: add_token_reservations
Revises: add_profile_runtime_toolsets
Create Date: 2026-07-23
"""
from alembic import op
import sqlalchemy as sa


revision = "add_token_reservations"
down_revision = "add_profile_runtime_toolsets"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "token_reservations",
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("profile_id", sa.UUID(), nullable=True),
        sa.Column("api_key_id", sa.UUID(), nullable=True),
        sa.Column("quota_date", sa.String(length=10), nullable=False),
        sa.Column("reserved_tokens", sa.BigInteger(), nullable=False),
        sa.Column("actual_tokens", sa.BigInteger(), nullable=True),
        sa.Column("status", sa.String(length=20), server_default="reserved", nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.ForeignKeyConstraint(["api_key_id"], ["user_api_keys.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["profile_id"], ["profiles.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in ("user_id", "profile_id", "api_key_id", "quota_date", "status", "expires_at"):
        op.create_index(f"ix_token_reservations_{column}", "token_reservations", [column])


def downgrade() -> None:
    op.drop_table("token_reservations")
