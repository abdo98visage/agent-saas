"""Token tracking service — quota checks and usage recording."""
import datetime
import json
from typing import Optional
from zoneinfo import ZoneInfo

from sqlalchemy import select, update, cast, func
from sqlalchemy.dialects.postgresql import JSONB, insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.kpi import KPI
from app.models.user_api_key import UserApiKey
from app.models.profile import Profile
from app.models.agent_run import AgentRun
from app.models.token_reservation import TokenReservation
from app.core.config import settings
from app.core.db import async_session


class TokenQuotaExceeded(RuntimeError):
    pass


def current_quota_date(now: datetime.datetime | None = None) -> str:
    current = now or datetime.datetime.now(datetime.timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=datetime.timezone.utc)
    return current.astimezone(ZoneInfo(settings.quota_timezone)).date().isoformat()


async def _get_today_kpi(db: AsyncSession, user_id: str) -> KPI | None:
    today = current_quota_date()
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


def _quota_day_start_utc(quota_date: str) -> datetime.datetime:
    local_start = datetime.datetime.combine(
        datetime.date.fromisoformat(quota_date),
        datetime.time.min,
        tzinfo=ZoneInfo(settings.quota_timezone),
    )
    return local_start.astimezone(datetime.timezone.utc).replace(tzinfo=None)


async def _active_reserved_tokens(
    db: AsyncSession,
    *,
    now: datetime.datetime,
    quota_date: str,
    user_id: str | None = None,
    profile_id: str | None = None,
    api_key_id: str | None = None,
) -> int:
    query = select(func.coalesce(func.sum(TokenReservation.reserved_tokens), 0)).where(
        TokenReservation.status == "reserved",
        TokenReservation.expires_at > now,
        TokenReservation.quota_date == quota_date,
    )
    if user_id:
        query = query.where(TokenReservation.user_id == user_id)
    if profile_id:
        query = query.where(TokenReservation.profile_id == profile_id)
    if api_key_id:
        query = query.where(TokenReservation.api_key_id == api_key_id)
    result = await db.execute(query)
    return int(result.scalar() or 0)


async def reserve_token_quota(
    *,
    user_id: str,
    user_daily_limit: int,
    requested_tokens: int,
    provider: str,
    profile_id: str | None = None,
    profile_daily_limit: int | None = None,
    api_key_id: str | None = None,
) -> str:
    """Atomically reserve worst-case tokens before an inference request starts."""
    now = datetime.datetime.utcnow()
    quota_date = current_quota_date(now.replace(tzinfo=datetime.timezone.utc))
    requested = max(1, int(requested_tokens))
    expires_at = now + datetime.timedelta(minutes=settings.token_reservation_ttl_minutes)

    async with async_session.begin() as db:
        await db.execute(
            update(TokenReservation)
            .where(
                TokenReservation.status == "reserved",
                TokenReservation.expires_at <= now,
            )
            .values(status="expired")
        )
        await db.execute(
            insert(KPI)
            .values(
                user_id=user_id,
                date=quota_date,
                messages_sent=0,
                tasks_completed=0,
                active_minutes=0,
                tools_used=[],
                tokens_used=0,
                total_cost=0.0,
                models_used={},
            )
            .on_conflict_do_nothing(constraint="uq_kpis_user_date")
        )
        kpi_result = await db.execute(
            select(KPI)
            .where(KPI.user_id == user_id, KPI.date == quota_date)
            .with_for_update()
        )
        kpi = kpi_result.scalar_one()
        user_reserved = await _active_reserved_tokens(
            db,
            now=now,
            quota_date=quota_date,
            user_id=user_id,
        )
        if int(kpi.tokens_used or 0) + user_reserved + requested > int(user_daily_limit):
            raise TokenQuotaExceeded("Daily user token quota would be exceeded")

        profile_uuid = None
        if profile_id:
            # Serialize profile reservations without conflicting with FK key-share
            # locks held by the request transaction while it creates a Session.
            await db.execute(
                select(
                    func.pg_advisory_xact_lock(
                        func.hashtextextended(f"token-profile:{profile_id}", 0)
                    )
                )
            )
            profile_result = await db.execute(
                select(Profile).where(Profile.id == profile_id)
            )
            profile = profile_result.scalar_one_or_none()
            profile_uuid = profile.id if profile else None
            effective_profile_limit = profile_daily_limit or (profile.max_tokens_per_day if profile else None)
            if effective_profile_limit:
                consumed_result = await db.execute(
                    select(
                        func.coalesce(
                            func.sum(AgentRun.input_tokens + AgentRun.output_tokens),
                            0,
                        )
                    ).where(
                        AgentRun.profile_id == profile_uuid,
                        AgentRun.status == "completed",
                        AgentRun.created_at >= _quota_day_start_utc(quota_date),
                    )
                )
                profile_reserved = await _active_reserved_tokens(
                    db,
                    now=now,
                    quota_date=quota_date,
                    profile_id=str(profile_uuid),
                )
                if int(consumed_result.scalar() or 0) + profile_reserved + requested > int(effective_profile_limit):
                    raise TokenQuotaExceeded("Daily profile token quota would be exceeded")

        key_uuid = None
        if api_key_id:
            key_result = await db.execute(
                select(UserApiKey).where(UserApiKey.id == api_key_id).with_for_update()
            )
            key_obj = key_result.scalar_one_or_none()
            if not key_obj or not key_obj.is_active or key_obj.provider != provider:
                raise TokenQuotaExceeded("Provider API key is unavailable for quota reservation")
            key_uuid = key_obj.id
            key_reserved = await _active_reserved_tokens(
                db,
                now=now,
                quota_date=quota_date,
                api_key_id=str(key_uuid),
            )
            if int(key_obj.spent_today or 0) + key_reserved + requested > int(key_obj.daily_budget):
                raise TokenQuotaExceeded("Provider API key daily token budget would be exceeded")

        reservation = TokenReservation(
            user_id=user_id,
            profile_id=profile_uuid,
            api_key_id=key_uuid,
            quota_date=quota_date,
            reserved_tokens=requested,
            status="reserved",
            expires_at=expires_at,
        )
        db.add(reservation)
        await db.flush()
        return str(reservation.id)


async def settle_token_reservation(
    reservation_id: str,
    *,
    model: str,
    actual_tokens: int,
    cost: float,
) -> None:
    """Settle a reservation exactly once and record usage against its original key."""
    actual = max(0, int(actual_tokens))
    async with async_session.begin() as db:
        result = await db.execute(
            select(TokenReservation)
            .where(TokenReservation.id == reservation_id)
            .with_for_update()
        )
        reservation = result.scalar_one_or_none()
        if not reservation or reservation.status != "reserved":
            return
        reservation.status = "settled"
        reservation.actual_tokens = actual
        await db.execute(
            insert(KPI)
            .values(
                user_id=reservation.user_id,
                date=reservation.quota_date,
                messages_sent=0,
                tasks_completed=0,
                active_minutes=0,
                tools_used=[],
                tokens_used=actual,
                total_cost=cost,
                models_used={},
            )
            .on_conflict_do_update(
                constraint="uq_kpis_user_date",
                set_={
                    "tokens_used": KPI.tokens_used + actual,
                    "total_cost": KPI.total_cost + cost,
                },
            )
        )
        kpi_result = await db.execute(
            select(KPI)
            .where(KPI.user_id == reservation.user_id, KPI.date == reservation.quota_date)
            .with_for_update()
        )
        kpi = kpi_result.scalar_one()
        models = dict(kpi.models_used or {})
        models[model] = int(models.get(model, 0)) + actual
        kpi.models_used = models
        if reservation.api_key_id:
            await db.execute(
                update(UserApiKey)
                .where(UserApiKey.id == reservation.api_key_id)
                .values(spent_today=UserApiKey.spent_today + actual)
            )


async def release_token_reservation(reservation_id: str) -> None:
    """Release unused quota after a failed or cancelled inference request."""
    async with async_session.begin() as db:
        await db.execute(
            update(TokenReservation)
            .where(
                TokenReservation.id == reservation_id,
                TokenReservation.status == "reserved",
            )
            .values(status="released", actual_tokens=0)
        )


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


async def reserve_request_quota(
    db: AsyncSession,
    user_id: str,
    max_requests_per_day: int,
) -> bool:
    """Atomically count an attempted request only when the daily limit allows it."""
    today = current_quota_date()
    statement = (
        insert(KPI)
        .values(
            user_id=user_id,
            date=today,
            messages_sent=1,
            tasks_completed=0,
            active_minutes=0,
            tools_used=[],
            tokens_used=0,
            total_cost=0.0,
            models_used={},
        )
        .on_conflict_do_update(
            constraint="uq_kpis_user_date",
            set_={"messages_sent": KPI.messages_sent + 1},
            where=KPI.messages_sent < max_requests_per_day,
        )
        .returning(KPI.id)
    )
    result = await db.execute(statement)
    return result.scalar_one_or_none() is not None


async def increment_message_count(db: AsyncSession, user_id: str) -> None:
    """Atomically increment KPI for internal/admin flows without a user quota."""
    today = current_quota_date()
    await db.execute(
        insert(KPI)
        .values(
            user_id=user_id,
            date=today,
            messages_sent=1,
            tasks_completed=0,
            active_minutes=0,
            tools_used=[],
            tokens_used=0,
            total_cost=0.0,
            models_used={},
        )
        .on_conflict_do_update(
            constraint="uq_kpis_user_date",
            set_={"messages_sent": KPI.messages_sent + 1},
        )
    )


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
    today = current_quota_date()
    await db.execute(
        insert(KPI)
        .values(
            user_id=user_id,
            date=today,
            messages_sent=0,
            tasks_completed=0,
            active_minutes=0,
            tools_used=[],
            tokens_used=tokens_used,
            total_cost=cost,
            models_used={},
        )
        .on_conflict_do_update(
            constraint="uq_kpis_user_date",
            set_={
                "tokens_used": KPI.tokens_used + tokens_used,
                "total_cost": KPI.total_cost + cost,
            },
        )
    )
    kpi_result = await db.execute(
        select(KPI)
        .where(KPI.user_id == user_id, KPI.date == today)
        .with_for_update()
    )
    kpi = kpi_result.scalar_one()
    models = dict(kpi.models_used or {})
    models[model] = int(models.get(model, 0)) + tokens_used
    kpi.models_used = models

    active_key = await _resolve_active_key(db, user_id, provider, profile_id)
    if active_key:
        await db.execute(
            update(UserApiKey)
            .where(UserApiKey.id == active_key.id)
            .values(spent_today=UserApiKey.spent_today + tokens_used)
        )


async def reset_daily_usage(db: AsyncSession):
    """Reset daily spent counters for API keys (called via Celery beat)."""
    stmt = update(UserApiKey).values(spent_today=0)
    await db.execute(stmt)
    await db.commit()
