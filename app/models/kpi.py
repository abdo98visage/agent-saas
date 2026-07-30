from sqlalchemy import Integer, Float, ForeignKey, String, BigInteger, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import UUIDPrimaryKeyMixin
from app.core.db import Base
from app.core.config import settings
from uuid import UUID


class KPI(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "kpis"
    __table_args__ = (UniqueConstraint("user_id", "date", name="uq_kpis_user_date"),)

    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    date: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    tasks_completed: Mapped[int] = mapped_column(Integer, default=0)
    messages_sent: Mapped[int] = mapped_column(Integer, default=0)
    avg_response_quality: Mapped[float] = mapped_column(Float, nullable=True)
    active_minutes: Mapped[int] = mapped_column(Integer, default=0)
    tools_used: Mapped[list] = mapped_column(JSONB, default=list)
    # Token tracking (added for cost monitoring)
    tokens_used: Mapped[int] = mapped_column(BigInteger, default=0)
    total_cost: Mapped[float] = mapped_column(Float, default=0.0)
    models_used: Mapped[dict] = mapped_column(JSONB, default=dict)

    @property
    def cost_alert(self) -> bool:
        """Check if this KPI exceeds token or cost alert thresholds."""
        return (
            self.tokens_used > settings.kpi_token_alert_threshold
            or self.total_cost > settings.kpi_cost_alert_threshold
        )
