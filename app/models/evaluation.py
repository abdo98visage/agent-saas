from datetime import datetime
from uuid import UUID

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin


class EvaluationSuite(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "evaluation_suites"

    name: Mapped[str] = mapped_column(String(150), nullable=False)
    profile_id: Mapped[UUID | None] = mapped_column(ForeignKey("profiles.id", ondelete="CASCADE"), index=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    cases: Mapped[list] = mapped_column(JSONB, default=list)
    thresholds: Mapped[dict] = mapped_column(JSONB, default=dict)
    baseline_run_id: Mapped[UUID | None] = mapped_column(nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)


class EvaluationRun(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "evaluation_runs"

    suite_id: Mapped[UUID] = mapped_column(ForeignKey("evaluation_suites.id", ondelete="CASCADE"), index=True)
    profile_id: Mapped[UUID | None] = mapped_column(ForeignKey("profiles.id", ondelete="SET NULL"), index=True)
    profile_version: Mapped[int | None] = mapped_column(Integer, index=True)
    triggered_by_user_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    status: Mapped[str] = mapped_column(String(24), default="running", index=True)
    candidate_label: Mapped[str | None] = mapped_column(String(100))
    metrics: Mapped[dict] = mapped_column(JSONB, default=dict)
    case_results: Mapped[list] = mapped_column(JSONB, default=list)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime)
    is_baseline: Mapped[bool] = mapped_column(Boolean, default=False, index=True)


class AgentFeedback(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "agent_feedback"
    __table_args__ = (UniqueConstraint("user_id", "agent_run_id", name="uq_agent_feedback_user_run"),)

    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    agent_run_id: Mapped[UUID] = mapped_column(ForeignKey("agent_runs.id", ondelete="CASCADE"), index=True)
    rating: Mapped[int] = mapped_column(Integer)
    outcome: Mapped[str] = mapped_column(String(20), index=True)
    tags: Mapped[list] = mapped_column(JSONB, default=list)
    note_hash: Mapped[str | None] = mapped_column(String(64))
