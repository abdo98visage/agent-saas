from sqlalchemy import BigInteger, String, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin
from app.core.db import Base
from uuid import UUID


class TelegramBinding(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "telegram_bindings"

    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    telegram_chat_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False, index=True)
    binding_token: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
