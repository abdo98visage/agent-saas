from datetime import datetime
from uuid import UUID

from sqlalchemy import BigInteger, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin


class TokenReservation(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "token_reservations"

    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    profile_id: Mapped[UUID] = mapped_column(
        ForeignKey("profiles.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    api_key_id: Mapped[UUID] = mapped_column(
        ForeignKey("user_api_keys.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    quota_date: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    reserved_tokens: Mapped[int] = mapped_column(BigInteger, nullable=False)
    actual_tokens: Mapped[int] = mapped_column(BigInteger, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="reserved", nullable=False, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
