from sqlalchemy import String, Boolean, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin
from app.core.db import Base
from uuid import UUID


class UserApiKey(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "user_api_keys"

    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    provider: Mapped[str] = mapped_column(String(50), default="minimax")  # minimax, openai, etc.
    encrypted_key: Mapped[str] = mapped_column(Text, nullable=False)  # Fernet encrypted
    key_prefix: Mapped[str] = mapped_column(String(10), nullable=False)  # First 6 chars for display
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    daily_budget: Mapped[int] = mapped_column(default=50000)  # Max tokens per day for this key
    spent_today: Mapped[int] = mapped_column(default=0)  # Reset daily

    user: Mapped["User"] = relationship(back_populates="api_keys")
