"""add idempotency keys for desktop messages

Revision ID: add_message_idempotency
Revises: harden_telegram_bindings
Create Date: 2026-07-23
"""
from alembic import op
import sqlalchemy as sa


revision = "add_message_idempotency"
down_revision = "harden_telegram_bindings"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("messages", sa.Column("client_message_id", sa.UUID(), nullable=True))
    op.create_unique_constraint(
        "uq_messages_session_client_message",
        "messages",
        ["session_id", "client_message_id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_messages_session_client_message",
        "messages",
        type_="unique",
    )
    op.drop_column("messages", "client_message_id")
