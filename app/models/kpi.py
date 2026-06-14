from sqlalchemy import Date, Integer, Float, ForeignKey, String, BigInteger
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import UUIDPrimaryKeyMixin
from app.core.db import Base
from uuid import UUID


class KPI(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "kpis"

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
        """Check if this KPI exceeds the cost alert threshold."""
        return self.tokens_used > 40000  # Alert at 40k tokens/day
