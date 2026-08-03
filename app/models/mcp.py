import sqlalchemy as sa
from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from uuid import UUID

from app.core.db import Base
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin


class McpServer(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "mcp_servers"

    name: Mapped[str] = mapped_column(String(100), nullable=False)
    slug: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    description: Mapped[str] = mapped_column(Text, default="")
    url: Mapped[str] = mapped_column(String(2048), nullable=False)
    auth_type: Mapped[str] = mapped_column(String(20), default="none", nullable=False)
    credential_mode: Mapped[str] = mapped_column(String(20), default="user", nullable=False)
    api_key_header: Mapped[str] = mapped_column(String(100), default="Authorization", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    discovered_tools: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    tools_schema_hash: Mapped[str] = mapped_column(String(64), default="", nullable=False)
    last_checked_at: Mapped[DateTime] = mapped_column(DateTime, nullable=True)
    last_error: Mapped[str] = mapped_column(Text, nullable=True)

    connections: Mapped[list["McpConnection"]] = relationship(
        back_populates="server",
        cascade="all, delete-orphan",
    )
    profile_bindings: Mapped[list["ProfileMcpBinding"]] = relationship(
        back_populates="server",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        sa.CheckConstraint(
            "auth_type IN ('none', 'bearer', 'api_key', 'oauth')",
            name="ck_mcp_servers_auth_type",
        ),
        sa.CheckConstraint(
            "credential_mode IN ('platform', 'user')",
            name="ck_mcp_servers_credential_mode",
        ),
    )


class McpConnection(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "mcp_connections"

    server_id: Mapped[UUID] = mapped_column(
        ForeignKey("mcp_servers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    owner_type: Mapped[str] = mapped_column(String(20), default="user", nullable=False, index=True)
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    encrypted_credentials: Mapped[str] = mapped_column(Text, default="", nullable=False)
    credential_hint: Mapped[str] = mapped_column(String(20), default="", nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False, index=True)
    discovered_tools: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    tools_schema_hash: Mapped[str] = mapped_column(String(64), default="", nullable=False)
    last_checked_at: Mapped[DateTime] = mapped_column(DateTime, nullable=True)
    last_error: Mapped[str] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)

    server: Mapped["McpServer"] = relationship(back_populates="connections")

    __table_args__ = (
        sa.CheckConstraint(
            "owner_type IN ('platform', 'user')",
            name="ck_mcp_connections_owner_type",
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'connected', 'error', 'disabled')",
            name="ck_mcp_connections_status",
        ),
        sa.CheckConstraint(
            "(owner_type = 'platform' AND user_id IS NULL) OR "
            "(owner_type = 'user' AND user_id IS NOT NULL)",
            name="ck_mcp_connections_owner_scope",
        ),
        sa.UniqueConstraint("server_id", "user_id", name="uq_mcp_connections_server_user"),
        sa.Index(
            "uq_mcp_connections_platform_server",
            "server_id",
            unique=True,
            postgresql_where=sa.text("owner_type = 'platform'"),
        ),
    )


class ProfileMcpBinding(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "profile_mcp_bindings"

    profile_id: Mapped[UUID] = mapped_column(
        ForeignKey("profiles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    server_id: Mapped[UUID] = mapped_column(
        ForeignKey("mcp_servers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    allowed_tools: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    approval_required_tools: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)

    server: Mapped["McpServer"] = relationship(back_populates="profile_bindings")

    __table_args__ = (
        sa.UniqueConstraint("profile_id", "server_id", name="uq_profile_mcp_binding"),
    )
