import sqlalchemy as sa
from sqlalchemy import String, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin
from app.core.db import Base
from uuid import UUID


class ProfileUser(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "profile_users"

    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    profile_id: Mapped[UUID] = mapped_column(ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False)
    priority: Mapped[int] = mapped_column(default=0)  # Priority order for multiple profiles

    user: Mapped["User"] = relationship(back_populates="profile_users")
    profile: Mapped["Profile"] = relationship(back_populates="profile_users")

    __table_args__ = (
        # Unique constraint: user can't have same profile twice
        sa.UniqueConstraint("user_id", "profile_id", name="uq_profile_user_user_profile"),
    )
