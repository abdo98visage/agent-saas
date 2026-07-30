"""add persistent account lockout state

Revision ID: add_account_lockout
Revises: add_message_idempotency
Create Date: 2026-07-23
"""
from alembic import op
import sqlalchemy as sa


revision = "add_account_lockout"
down_revision = "add_message_idempotency"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("failed_login_attempts", sa.Integer(), server_default="0", nullable=False),
    )
    op.add_column("users", sa.Column("locked_until", sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "locked_until")
    op.drop_column("users", "failed_login_attempts")
