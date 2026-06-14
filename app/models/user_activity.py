"""User Activity Log — Tracks every employee action in real-time."""
from sqlalchemy import BigInteger, String, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import TimestampMixin
from app.core.db import Base
from uuid import UUID


class UserActivity(Base, TimestampMixin):
    __tablename__ = "user_activities"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    action: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    details: Mapped[dict] = mapped_column(JSONB, default=dict)
    session_id: Mapped[UUID] = mapped_column(ForeignKey("sessions.id"), nullable=True, index=True)
