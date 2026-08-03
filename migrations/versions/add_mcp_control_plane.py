"""add MCP control plane tables

Revision ID: add_mcp_control_plane
Revises: add_token_reservations
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "add_mcp_control_plane"
down_revision: Union[str, None] = "add_token_reservations"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "mcp_servers",
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("slug", sa.String(length=64), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("url", sa.String(length=2048), nullable=False),
        sa.Column("auth_type", sa.String(length=20), nullable=False, server_default="none"),
        sa.Column("credential_mode", sa.String(length=20), nullable=False, server_default="user"),
        sa.Column("api_key_header", sa.String(length=100), nullable=False, server_default="Authorization"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("discovered_tools", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="[]"),
        sa.Column("tools_schema_hash", sa.String(length=64), nullable=False, server_default=""),
        sa.Column("last_checked_at", sa.DateTime(), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("auth_type IN ('none', 'bearer', 'api_key', 'oauth')", name="ck_mcp_servers_auth_type"),
        sa.CheckConstraint("credential_mode IN ('platform', 'user')", name="ck_mcp_servers_credential_mode"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_mcp_servers_slug"), "mcp_servers", ["slug"], unique=True)
    op.create_index(op.f("ix_mcp_servers_is_active"), "mcp_servers", ["is_active"], unique=False)

    op.create_table(
        "mcp_connections",
        sa.Column("server_id", sa.UUID(), nullable=False),
        sa.Column("owner_type", sa.String(length=20), nullable=False, server_default="user"),
        sa.Column("user_id", sa.UUID(), nullable=True),
        sa.Column("encrypted_credentials", sa.Text(), nullable=False, server_default=""),
        sa.Column("credential_hint", sa.String(length=20), nullable=False, server_default=""),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("discovered_tools", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="[]"),
        sa.Column("tools_schema_hash", sa.String(length=64), nullable=False, server_default=""),
        sa.Column("last_checked_at", sa.DateTime(), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("owner_type IN ('platform', 'user')", name="ck_mcp_connections_owner_type"),
        sa.CheckConstraint("status IN ('pending', 'connected', 'error', 'disabled')", name="ck_mcp_connections_status"),
        sa.CheckConstraint("(owner_type = 'platform' AND user_id IS NULL) OR (owner_type = 'user' AND user_id IS NOT NULL)", name="ck_mcp_connections_owner_scope"),
        sa.ForeignKeyConstraint(["server_id"], ["mcp_servers.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("server_id", "user_id", name="uq_mcp_connections_server_user"),
    )
    op.create_index(op.f("ix_mcp_connections_server_id"), "mcp_connections", ["server_id"], unique=False)
    op.create_index(op.f("ix_mcp_connections_user_id"), "mcp_connections", ["user_id"], unique=False)
    op.create_index(op.f("ix_mcp_connections_owner_type"), "mcp_connections", ["owner_type"], unique=False)
    op.create_index(op.f("ix_mcp_connections_status"), "mcp_connections", ["status"], unique=False)
    op.create_index(op.f("ix_mcp_connections_is_active"), "mcp_connections", ["is_active"], unique=False)
    op.create_index("uq_mcp_connections_platform_server", "mcp_connections", ["server_id"], unique=True, postgresql_where=sa.text("owner_type = 'platform'"))

    op.create_table(
        "profile_mcp_bindings",
        sa.Column("profile_id", sa.UUID(), nullable=False),
        sa.Column("server_id", sa.UUID(), nullable=False),
        sa.Column("allowed_tools", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="[]"),
        sa.Column("approval_required_tools", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="[]"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["profile_id"], ["profiles.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["server_id"], ["mcp_servers.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("profile_id", "server_id", name="uq_profile_mcp_binding"),
    )
    op.create_index(op.f("ix_profile_mcp_bindings_profile_id"), "profile_mcp_bindings", ["profile_id"], unique=False)
    op.create_index(op.f("ix_profile_mcp_bindings_server_id"), "profile_mcp_bindings", ["server_id"], unique=False)
    op.create_index(op.f("ix_profile_mcp_bindings_is_active"), "profile_mcp_bindings", ["is_active"], unique=False)


def downgrade() -> None:
    op.drop_table("profile_mcp_bindings")
    op.drop_table("mcp_connections")
    op.drop_table("mcp_servers")
