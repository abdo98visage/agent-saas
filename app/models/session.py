from sqlalchemy import String, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin
from app.core.db import Base
from uuid import UUID


class Session(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "sessions"

    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=True)
    agent_template_name: Mapped[str] = mapped_column(String(50), nullable=True, index=True)
    last_activity: Mapped[str] = mapped_column(String(50), nullable=True)
    profile_name: Mapped[str] = mapped_column(String(100), nullable=True)  # Which profile was used
    profile_id: Mapped[UUID] = mapped_column(ForeignKey("profiles.id"), nullable=True, index=True)
    profile_version: Mapped[int] = mapped_column(Integer, nullable=True)

    user: Mapped["User"] = relationship(back_populates="sessions")
