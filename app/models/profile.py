from sqlalchemy import String, Text, ForeignKey, Integer, DateTime
from uuid import UUID
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin
from app.core.db import Base


class Profile(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "profiles"

    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    slug: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    agents_md: Mapped[str] = mapped_column(Text, default="")  # agents.md content
    soul_md: Mapped[str] = mapped_column(Text, default="")  # soul.md content
    skills: Mapped[list] = mapped_column(JSONB, default=list)  # ["skill1", "skill2"]
    system_prompt: Mapped[str] = mapped_column(Text, default="")
    is_active: Mapped[bool] = mapped_column(default=True, index=True)
    runtime_type: Mapped[str] = mapped_column(String(50), default="hermes", index=True)  # hermes or direct_llm
    hermes_profile_id: Mapped[str] = mapped_column(String(100), nullable=True, index=True)
    hermes_workspace_path: Mapped[str] = mapped_column(String(500), nullable=True)
    hermes_sync_status: Mapped[str] = mapped_column(String(50), default="pending", index=True)
    hermes_sync_error: Mapped[str] = mapped_column(Text, nullable=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    last_synced_at: Mapped[DateTime] = mapped_column(DateTime, nullable=True)
    provider_key_id: Mapped[UUID] = mapped_column(ForeignKey("user_api_keys.id"), nullable=True)
    max_tokens_per_day: Mapped[int] = mapped_column(Integer, nullable=True)
    max_requests_per_day: Mapped[int] = mapped_column(Integer, nullable=True)
    daily_cost_budget: Mapped[int] = mapped_column(Integer, nullable=True)
    allowed_providers: Mapped[list] = mapped_column(JSONB, default=list)
    allowed_mcp_servers: Mapped[list] = mapped_column(JSONB, default=list)
    allowed_tools: Mapped[list] = mapped_column(JSONB, default=list)
    approval_required_tools: Mapped[list] = mapped_column(JSONB, default=list)
    memory_settings: Mapped[dict] = mapped_column(JSONB, default=dict)

    # Relationships
    profile_users: Mapped[list["ProfileUser"]] = relationship(back_populates="profile", cascade="all, delete-orphan")
