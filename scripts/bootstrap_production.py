"""
Production bootstrap for one-command VPS deployments.

This script is intentionally separate from seed_templates.py so development
defaults can stay unchanged while production uses env-driven credentials and
encrypted platform provider keys.
"""
import asyncio
import os
import secrets

from cryptography.fernet import Fernet
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.core.security import get_password_hash
from app.models.agent_template import AgentTemplate
from app.models.provider_pricing import ProviderPricing
from app.models.skill_definition import SkillDefinition
from app.models.user import User
from app.models.user_api_key import UserApiKey
from seed_templates import DEFAULT_SKILLS, DEFAULT_TEMPLATES


def _required_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"{name} is required for production bootstrap")
    return value


def _generated_password() -> str:
    return secrets.token_urlsafe(24)


async def _ensure_admin(session: AsyncSession, email: str, password: str) -> str:
    result = await session.execute(select(User).where(User.email == email))
    admin = result.scalar_one_or_none()
    if admin:
        admin.role = "admin"
        admin.is_active = True
        admin.is_activated = True
        return "existing"

    session.add(
        User(
            email=email,
            hashed_password=get_password_hash(password),
            full_name="System Administrator",
            department="it",
            role="admin",
            is_active=True,
            is_activated=True,
            max_tokens_per_day=100000,
            max_requests_per_day=500,
        )
    )
    return "created"


async def _ensure_templates(session: AsyncSession) -> int:
    created = 0
    for template_data in DEFAULT_TEMPLATES:
        result = await session.execute(select(AgentTemplate).where(AgentTemplate.name == template_data["name"]))
        if result.scalar_one_or_none():
            continue
        session.add(AgentTemplate(**template_data))
        created += 1
    return created


async def _ensure_skills(session: AsyncSession) -> int:
    created = 0
    for skill_data in DEFAULT_SKILLS:
        result = await session.execute(select(SkillDefinition).where(SkillDefinition.slug == skill_data["slug"]))
        if result.scalar_one_or_none():
            continue
        session.add(SkillDefinition(**skill_data))
        created += 1
    return created


async def _ensure_platform_minimax_key(session: AsyncSession, api_key: str) -> str:
    result = await session.execute(
        select(UserApiKey).where(
            UserApiKey.owner_type == "platform",
            UserApiKey.user_id.is_(None),
            UserApiKey.profile_id.is_(None),
            UserApiKey.provider == "minimax",
            UserApiKey.is_active == True,
        )
    )
    key_obj = result.scalar_one_or_none()
    should_rotate = os.getenv("BOOTSTRAP_ROTATE_PLATFORM_KEY", "").lower() == "true"
    if key_obj and not should_rotate:
        return "existing"

    fernet = Fernet(settings.fernet_key.encode())
    encrypted = fernet.encrypt(api_key.encode()).decode()
    if key_obj:
        key_obj.encrypted_key = encrypted
        key_obj.key_prefix = api_key[:6]
        key_obj.daily_budget = int(os.getenv("MINIMAX_PLATFORM_KEY_DAILY_BUDGET", "10000000"))
        return "rotated"

    session.add(
        UserApiKey(
            owner_type="platform",
            user_id=None,
            profile_id=None,
            provider="minimax",
            encrypted_key=encrypted,
            key_prefix=api_key[:6],
            daily_budget=int(os.getenv("MINIMAX_PLATFORM_KEY_DAILY_BUDGET", "10000000")),
            is_active=True,
        )
    )
    return "created"


async def _ensure_minimax_pricing(session: AsyncSession) -> str:
    result = await session.execute(select(ProviderPricing).where(ProviderPricing.provider == "minimax"))
    pricing = result.scalar_one_or_none()
    monthly_price = float(os.getenv("MINIMAX_MONTHLY_PRICE_USD", "20"))
    allowance = int(os.getenv("MINIMAX_MONTHLY_TOKEN_ALLOWANCE", "1700000000"))
    if pricing:
        pricing.currency = os.getenv("MINIMAX_PRICING_CURRENCY", "USD")
        pricing.monthly_price_usd = monthly_price
        pricing.monthly_token_allowance = allowance
        pricing.is_active = True
        return "updated"

    session.add(
        ProviderPricing(
            provider="minimax",
            currency=os.getenv("MINIMAX_PRICING_CURRENCY", "USD"),
            monthly_price_usd=monthly_price,
            monthly_token_allowance=allowance,
            is_active=True,
        )
    )
    return "created"


async def bootstrap() -> None:
    if settings.environment.lower() != "production":
        raise RuntimeError("scripts/bootstrap_production.py must only run with ENVIRONMENT=production")

    admin_email = _required_env("ADMIN_EMAIL")
    admin_password = os.getenv("ADMIN_PASSWORD", "").strip() or _generated_password()
    minimax_key = _required_env("MINIMAX_API_KEY")

    engine = create_async_engine(settings.database_url)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        admin_status = await _ensure_admin(session, admin_email, admin_password)
        templates_created = await _ensure_templates(session)
        skills_created = await _ensure_skills(session)
        platform_key_status = await _ensure_platform_minimax_key(session, minimax_key)
        pricing_status = await _ensure_minimax_pricing(session)
        await session.commit()

    await engine.dispose()

    print("Production bootstrap complete.")
    print(f"Admin: {admin_email} ({admin_status})")
    print(f"Templates created: {templates_created}")
    print(f"Skills created: {skills_created}")
    print(f"MiniMax platform key: {platform_key_status}")
    print(f"MiniMax pricing: {pricing_status}")


if __name__ == "__main__":
    asyncio.run(bootstrap())
