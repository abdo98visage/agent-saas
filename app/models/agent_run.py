from datetime import datetime
from uuid import UUID

from sqlalchemy import String, ForeignKey, DateTime, Integer, Float, BigInteger, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin
from app.core.audit_context import current_trace_id


class AgentRun(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "agent_runs"

    session_id: Mapped[UUID] = mapped_column(ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    profile_id: Mapped[UUID] = mapped_column(ForeignKey("profiles.id"), nullable=True, index=True)
    profile_version: Mapped[int] = mapped_column(Integer, nullable=True)
    runtime_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(50), default="running", index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    ended_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    latency_ms: Mapped[int] = mapped_column(Integer, nullable=True)
    input_tokens: Mapped[int] = mapped_column(BigInteger, default=0)
    output_tokens: Mapped[int] = mapped_column(BigInteger, default=0)
    total_cost: Mapped[float] = mapped_column(Float, default=0.0)
    pricing_snapshot: Mapped[dict] = mapped_column(JSONB, default=dict)
    model: Mapped[str] = mapped_column(String(100), nullable=True)
    provider: Mapped[str] = mapped_column(String(50), nullable=True)
    tools_used: Mapped[list] = mapped_column(JSONB, default=list)
    mcp_servers_used: Mapped[list] = mapped_column(JSONB, default=list)
    error_code: Mapped[str] = mapped_column(String(100), nullable=True)
    error_message: Mapped[str] = mapped_column(Text, nullable=True)
    trace_id: Mapped[str] = mapped_column(String(64), default=current_trace_id, nullable=True, index=True)

    events: Mapped[list["AgentRunEvent"]] = relationship(back_populates="run", cascade="all, delete-orphan")


class AgentRunEvent(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "agent_run_events"

    run_id: Mapped[UUID] = mapped_column(ForeignKey("agent_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    payload: Mapped[dict] = mapped_column(JSONB, default=dict)

    run: Mapped["AgentRun"] = relationship(back_populates="events")
