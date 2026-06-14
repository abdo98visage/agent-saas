import secrets
from datetime import datetime
from sqlalchemy import String, Boolean, Integer, Index, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin
from app.core.db import Base
from uuid import UUID


class User(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(100), nullable=True)
    department: Mapped[str] = mapped_column(String(50), nullable=True, index=True)
    role: Mapped[str] = mapped_column(String(20), default="employee", index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    is_activated: Mapped[bool] = mapped_column(Boolean, default=True, index=True)  # Employee must activate via invite
    invite_token: Mapped[str] = mapped_column(String(64), nullable=True, index=True)  # One-time activation token
    max_tokens_per_day: Mapped[int] = mapped_column(Integer, default=50000)
    max_requests_per_day: Mapped[int] = mapped_column(Integer, default=200)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)  # Desktop online tracking

    # Relationships
    profile_users: Mapped[list["ProfileUser"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    api_keys: Mapped[list["UserApiKey"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    sessions: Mapped[list["Session"]] = relationship(back_populates="user")
