"""allow multiple pending Telegram bindings

Revision ID: pending_telegram_bindings
Revises: prohibit_execution_tools
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "pending_telegram_bindings"
down_revision: Union[str, None] = "prohibit_execution_tools"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_index("ix_telegram_bindings_telegram_chat_id", table_name="telegram_bindings")
    op.create_index(
        "ix_telegram_bindings_telegram_chat_id",
        "telegram_bindings",
        ["telegram_chat_id"],
        unique=False,
    )
    op.create_index(
        "uq_telegram_bindings_bound_chat_id",
        "telegram_bindings",
        ["telegram_chat_id"],
        unique=True,
        postgresql_where=sa.text("telegram_chat_id <> 0"),
    )


def downgrade() -> None:
    op.drop_index("uq_telegram_bindings_bound_chat_id", table_name="telegram_bindings")
    op.drop_index("ix_telegram_bindings_telegram_chat_id", table_name="telegram_bindings")
    op.execute(
        """
        DELETE FROM telegram_bindings
        WHERE telegram_chat_id = 0
          AND id NOT IN (
              SELECT id FROM telegram_bindings
              WHERE telegram_chat_id = 0
              ORDER BY created_at ASC
              LIMIT 1
          )
        """
    )
    op.create_index(
        "ix_telegram_bindings_telegram_chat_id",
        "telegram_bindings",
        ["telegram_chat_id"],
        unique=True,
    )
