from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.provider_pricing import ProviderPricing


@dataclass
class CostCalculation:
    total_cost: float
    pricing_snapshot: dict


class PricingService:
    async def get_active_pricing(self, db: AsyncSession, provider: str) -> Optional[ProviderPricing]:
        result = await db.execute(
            select(ProviderPricing)
            .where(
                ProviderPricing.provider == provider,
                ProviderPricing.is_active == True,
            )
            .order_by(desc(ProviderPricing.updated_at), desc(ProviderPricing.created_at))
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def calculate_cost(
        self,
        db: AsyncSession,
        provider: str,
        input_tokens: int,
        output_tokens: int,
        fallback_cost: float = 0.0,
    ) -> CostCalculation:
        pricing = await self.get_active_pricing(db, provider)
        total_tokens = max(0, int(input_tokens or 0)) + max(0, int(output_tokens or 0))

        if not pricing or pricing.monthly_token_allowance <= 0 or pricing.monthly_price_usd <= 0:
            return CostCalculation(
                total_cost=round(float(fallback_cost or 0.0), 6),
                pricing_snapshot={
                    "provider": provider,
                    "source": "runtime_fallback",
                    "input_tokens": int(input_tokens or 0),
                    "output_tokens": int(output_tokens or 0),
                    "total_tokens": total_tokens,
                    "fallback_cost": round(float(fallback_cost or 0.0), 6),
                },
            )

        usd_per_token = pricing.monthly_price_usd / pricing.monthly_token_allowance
        total_cost = round(total_tokens * usd_per_token, 6)
        return CostCalculation(
            total_cost=total_cost,
            pricing_snapshot={
                "provider": provider,
                "source": "configured_monthly_plan",
                "pricing_id": str(pricing.id),
                "currency": pricing.currency,
                "monthly_price_usd": round(float(pricing.monthly_price_usd), 6),
                "monthly_token_allowance": int(pricing.monthly_token_allowance),
                "usd_per_1m_tokens": round(usd_per_token * 1_000_000, 6),
                "input_tokens": int(input_tokens or 0),
                "output_tokens": int(output_tokens or 0),
                "total_tokens": total_tokens,
            },
        )


pricing_service = PricingService()
