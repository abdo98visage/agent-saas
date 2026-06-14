from sqlalchemy import DateTime, func, UUID as SQLA_UUID, String
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime
from uuid import UUID, uuid4


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), onupdate=func.now())


class UUIDPrimaryKeyMixin:
    id: Mapped[UUID] = mapped_column(SQLA_UUID, primary_key=True, default=uuid4)
