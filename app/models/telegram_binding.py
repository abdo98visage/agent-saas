from datetime import datetime

from sqlalchemy import BigInteger, String, ForeignKey, DateTime
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin
from app.core.db import Base
from uuid import UUID


class TelegramBinding(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "telegram_bindings"

    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    # Zero represents a pending, not-yet-bound record. PostgreSQL enforces
    # uniqueness only for non-zero chat IDs through a partial unique index.
    telegram_chat_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    binding_token: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    binding_token_expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    session_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("sessions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
