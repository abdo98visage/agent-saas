"""add message attachments

Revision ID: add_message_attachments
Revises: merge_alert_and_skill_heads
Create Date: 2026-07-05
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "add_message_attachments"
down_revision = "add_profile_ids_to_user_api_keys"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("messages", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "attachments",
                postgresql.JSONB(astext_type=sa.Text()),
                nullable=False,
                server_default="[]",
            )
        )


def downgrade():
    with op.batch_alter_table("messages", schema=None) as batch_op:
        batch_op.drop_column("attachments")
