"""harden Telegram bindings and preserve conversation continuity

Revision ID: harden_telegram_bindings
Revises: add_kpi_user_date_unique
Create Date: 2026-07-23
"""
from alembic import op
import sqlalchemy as sa


revision = "harden_telegram_bindings"
down_revision = "add_kpi_user_date_unique"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("telegram_bindings", sa.Column("session_id", sa.UUID(), nullable=True))
    op.create_foreign_key(
        "fk_telegram_bindings_session_id_sessions",
        "telegram_bindings",
        "sessions",
        ["session_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        op.f("ix_telegram_bindings_session_id"),
        "telegram_bindings",
        ["session_id"],
        unique=False,
    )
    op.execute(
        """
        WITH duplicates AS (
            SELECT id, ROW_NUMBER() OVER (PARTITION BY binding_token ORDER BY id) AS row_number
            FROM telegram_bindings
        )
        UPDATE telegram_bindings AS binding
        SET binding_token = md5(binding.id::text || clock_timestamp()::text)
        FROM duplicates
        WHERE binding.id = duplicates.id AND duplicates.row_number > 1
        """
    )
    op.create_unique_constraint(
        "uq_telegram_bindings_binding_token",
        "telegram_bindings",
        ["binding_token"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_telegram_bindings_binding_token",
        "telegram_bindings",
        type_="unique",
    )
    op.drop_index(op.f("ix_telegram_bindings_session_id"), table_name="telegram_bindings")
    op.drop_constraint(
        "fk_telegram_bindings_session_id_sessions",
        "telegram_bindings",
        type_="foreignkey",
    )
    op.drop_column("telegram_bindings", "session_id")
