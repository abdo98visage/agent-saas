"""Token tracking service — quota checks and usage recording."""
import datetime
import json
from typing import Optional

from sqlalchemy import select, update, cast
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.kpi import KPI
from app.models.user_api_key import UserApiKey


async def _get_today_kpi(db: AsyncSession, user_id: str) -> KPI | None:
    today = datetime.date.today().isoformat()
    result = await db.execute(
        select(KPI).where(KPI.user_id == user_id, KPI.date == today)
    )
    return result.scalar_one_or_none()


async def _resolve_active_key(
    db: AsyncSession,
    user_id: str,
    provider: str,
    profile_id: Optional[str] = None,
) -> UserApiKey | None:
    candidates = [(UserApiKey.owner_type == "user", UserApiKey.user_id == user_id)]
    if profile_id:
        candidates.append((
            UserApiKey.owner_type == "profile",
            (UserApiKey.profile_id == profile_id) |
            (UserApiKey.profile_ids.op("@>")(cast(json.dumps([str(profile_id)]), JSONB))),
        ))
    candidates.append((UserApiKey.owner_type == "platform", UserApiKey.user_id.is_(None)))

    for owner_filter, id_filter in candidates:
        result = await db.execute(
            select(UserApiKey)
            .where(
                owner_filter,
                id_filter,
                UserApiKey.provider == provider,
                UserApiKey.is_active == True,
            )
            .limit(1)
        )
        key_obj = result.scalars().first()
        if key_obj:
            return key_obj
    return None


async def check_token_quota(
    db: AsyncSession,
    user_id: str,
    max_tokens_per_day: int,
    provider: str = "minimax",
    profile_id: Optional[str] = None,
) -> bool:
    """Check if the user or the active API key has exhausted today's token budget."""
    kpi = await _get_today_kpi(db, user_id)
    tokens_used = kpi.tokens_used if kpi else 0
    if tokens_used >= max_tokens_per_day:
        return False

    active_key = await _resolve_active_key(db, user_id, provider, profile_id)
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
    provider: str = "minimax",
    profile_id: Optional[str] = None,
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

    active_key = await _resolve_active_key(db, user_id, provider, profile_id)
    if active_key:
        active_key.spent_today += tokens_used


async def reset_daily_usage(db: AsyncSession):
    """Reset daily spent counters for API keys (called via Celery beat)."""
    stmt = update(UserApiKey).values(spent_today=0)
    await db.execute(stmt)
    await db.commit()
