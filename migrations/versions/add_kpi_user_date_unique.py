"""make daily KPI rows unique

Revision ID: add_kpi_user_date_unique
Revises: add_auth_sessions
Create Date: 2026-07-23
"""
from alembic import op
import sqlalchemy as sa


revision = "add_kpi_user_date_unique"
down_revision = "add_auth_sessions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        WITH totals AS (
            SELECT
                user_id,
                date,
                MIN(id::text)::uuid AS keeper_id,
                SUM(tasks_completed) AS tasks_completed,
                SUM(messages_sent) AS messages_sent,
                SUM(active_minutes) AS active_minutes,
                SUM(tokens_used) AS tokens_used,
                SUM(total_cost) AS total_cost
            FROM kpis
            GROUP BY user_id, date
        )
        UPDATE kpis AS target
        SET
            tasks_completed = totals.tasks_completed,
            messages_sent = totals.messages_sent,
            active_minutes = totals.active_minutes,
            tokens_used = totals.tokens_used,
            total_cost = totals.total_cost
        FROM totals
        WHERE target.id = totals.keeper_id
        """
    )
    op.execute(
        """
        DELETE FROM kpis AS duplicate
        USING kpis AS keeper
        WHERE duplicate.user_id = keeper.user_id
          AND duplicate.date = keeper.date
          AND duplicate.id::text > keeper.id::text
        """
    )
    op.create_unique_constraint("uq_kpis_user_date", "kpis", ["user_id", "date"])


def downgrade() -> None:
    op.drop_constraint("uq_kpis_user_date", "kpis", type_="unique")
