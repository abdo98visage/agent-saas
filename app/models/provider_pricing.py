from sqlalchemy import BigInteger, Boolean, Float, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin


class ProviderPricing(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "provider_pricing"

    provider: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    currency: Mapped[str] = mapped_column(String(8), nullable=False, default="USD")
    monthly_price_usd: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    monthly_token_allowance: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)
