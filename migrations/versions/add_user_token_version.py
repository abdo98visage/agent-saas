"""add token_version to users

Revision ID: add_user_token_version
Revises: add_token_expiry_fields
Create Date: 2026-06-21
"""
from alembic import op
import sqlalchemy as sa


revision = "add_user_token_version"
down_revision = "add_token_expiry_fields"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.add_column(sa.Column("token_version", sa.Integer(), nullable=False, server_default="0"))


def downgrade():
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.drop_column("token_version")
