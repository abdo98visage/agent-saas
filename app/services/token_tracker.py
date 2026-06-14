"""Token tracking service — quota checks and usage recording."""
import datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.kpi import KPI
from app.models.user_api_key import UserApiKey


async def _get_today_kpi(db: AsyncSession, user_id: str) -> KPI | None:
    today = datetime.date.today().isoformat()
    result = await db.execute(
        select(KPI).where(KPI.user_id == user_id, KPI.date == today)
    )
    return result.scalar_one_or_none()


async def check_token_quota(
    db: AsyncSession,
    user_id: str,
    max_tokens_per_day: int,
) -> bool:
    """Check if the user or the active API key has exhausted today's token budget."""
    kpi = await _get_today_kpi(db, user_id)
    tokens_used = kpi.tokens_used if kpi else 0
    if tokens_used >= max_tokens_per_day:
        return False

    key_result = await db.execute(
        select(UserApiKey).where(
            UserApiKey.user_id == user_id,
            UserApiKey.is_active == True,
        )
    )
    active_key = key_result.scalar_one_or_none()
    if active_key and active_key.spent_today >= active_key.daily_budget:
        return False

    return True


async def check_request_quota(
    db: AsyncSession,
    user_id: str,
    max_requests_per_day: int,
) -> bool:
    """Check if the user has exceeded today's request quota."""
    kpi = await _get_today_kpi(db, user_id)
    if kpi:
        return kpi.messages_sent < max_requests_per_day
    return True


async def record_token_usage(
    db: AsyncSession,
    user_id: str,
    model: str,
    tokens_used: int,
    cost: float,
):
    """Record token usage for a user and the active API key."""
    today = datetime.date.today().isoformat()
    kpi = await _get_today_kpi(db, user_id)

    if kpi:
        kpi.tokens_used += tokens_used
        kpi.total_cost += cost
        models = kpi.models_used or {}
        models[model] = models.get(model, 0) + tokens_used
        kpi.models_used = models
    else:
        kpi = KPI(
            user_id=user_id,
            date=today,
            messages_sent=0,
            tokens_used=tokens_used,
            total_cost=cost,
            models_used={model: tokens_used},
        )
        db.add(kpi)

    key_result = await db.execute(
        select(UserApiKey).where(
            UserApiKey.user_id == user_id,
            UserApiKey.is_active == True,
        )
    )
    active_key = key_result.scalar_one_or_none()
    if active_key:
        active_key.spent_today += tokens_used


async def reset_daily_usage(db: AsyncSession):
    """Reset daily spent counters for API keys (called via Celery beat)."""
    stmt = update(UserApiKey).values(spent_today=0)
    await db.execute(stmt)
    await db.commit()
