from sqlalchemy import String, Text, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin
from app.core.db import Base


class Profile(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "profiles"

    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    slug: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    agents_md: Mapped[str] = mapped_column(Text, default="")  # agents.md content
    soul_md: Mapped[str] = mapped_column(Text, default="")  # soul.md content
    skills: Mapped[list] = mapped_column(JSONB, default=list)  # ["skill1", "skill2"]
    system_prompt: Mapped[str] = mapped_column(Text, default="")
    is_active: Mapped[bool] = mapped_column(default=True, index=True)

    # Relationships
    profile_users: Mapped[list["ProfileUser"]] = relationship(back_populates="profile", cascade="all, delete-orphan")
