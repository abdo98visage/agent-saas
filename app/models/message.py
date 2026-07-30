from sqlalchemy import String, ForeignKey, Integer, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin
from app.core.db import Base
from uuid import UUID


class Message(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "messages"
    __table_args__ = (
        UniqueConstraint("session_id", "client_message_id", name="uq_messages_session_client_message"),
    )

    session_id: Mapped[UUID] = mapped_column(ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    client_message_id: Mapped[UUID | None] = mapped_column(nullable=True)
    role: Mapped[str] = mapped_column(String(20), nullable=False)  # user, assistant, system
    content: Mapped[str] = mapped_column(nullable=False)
    project_context: Mapped[str] = mapped_column(nullable=True)
    tokens_used: Mapped[int] = mapped_column(Integer, nullable=True)
    attachments: Mapped[list] = mapped_column(JSONB, nullable=False, default=list, server_default="[]")
