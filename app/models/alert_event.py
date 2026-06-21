from datetime import datetime

from sqlalchemy import Boolean, DateTime, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin


class AlertEvent(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "alert_events"

    alert_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    severity: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active", index=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    fingerprint: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    context: Mapped[dict] = mapped_column(JSONB, default=dict)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    last_notified_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    is_acknowledged: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
