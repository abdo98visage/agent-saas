"""add profile_ids to user_api_keys

Revision ID: add_profile_ids_to_user_api_keys
Revises: merge_alert_and_skill_heads
Create Date: 2026-07-02 11:15:00.000000
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "add_profile_ids_to_user_api_keys"
down_revision = "merge_alert_and_skill_heads"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("user_api_keys", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "profile_ids",
                postgresql.JSONB(astext_type=sa.Text()),
                nullable=False,
                server_default="[]",
            )
        )

    op.execute(
        """
        UPDATE user_api_keys
        SET profile_ids = jsonb_build_array(profile_id::text)
        WHERE profile_id IS NOT NULL
        """
    )


def downgrade() -> None:
    with op.batch_alter_table("user_api_keys", schema=None) as batch_op:
        batch_op.drop_column("profile_ids")
