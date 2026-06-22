"""add invite and telegram binding token expiry fields

Revision ID: add_token_expiry_fields
Revises: add_provider_pricing_snapshot
Create Date: 2026-06-21
"""
from alembic import op
import sqlalchemy as sa


revision = "add_token_expiry_fields"
down_revision = "add_provider_pricing_snapshot"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.add_column(sa.Column("invite_token_expires_at", sa.DateTime(), nullable=True))

    with op.batch_alter_table("telegram_bindings", schema=None) as batch_op:
        batch_op.add_column(sa.Column("binding_token_expires_at", sa.DateTime(), nullable=True))


def downgrade():
    with op.batch_alter_table("telegram_bindings", schema=None) as batch_op:
        batch_op.drop_column("binding_token_expires_at")

    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.drop_column("invite_token_expires_at")
