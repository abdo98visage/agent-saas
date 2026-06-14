from sqlalchemy import String, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin
from app.core.db import Base
from uuid import UUID


class Message(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "messages"

    session_id: Mapped[UUID] = mapped_column(ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    role: Mapped[str] = mapped_column(String(20), nullable=False)  # user, assistant, system
    content: Mapped[str] = mapped_column(nullable=False)
    project_context: Mapped[str] = mapped_column(nullable=True)
    tokens_used: Mapped[int] = mapped_column(Integer, nullable=True)
