from typing import Optional
from uuid import UUID

from cryptography.fernet import Fernet
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.user_api_key import UserApiKey


class ApiKeyResolver:
    """Resolve provider keys in employee override -> profile -> platform order."""

    def __init__(self) -> None:
        self._fernet: Optional[Fernet] = None

    def decrypt(self, key_obj: UserApiKey) -> str:
        if not self._fernet:
            self._fernet = Fernet(settings.fernet_key.encode())
        return self._fernet.decrypt(key_obj.encrypted_key.encode()).decode()

    async def resolve_key(
        self,
        db: AsyncSession,
        user_id: UUID,
        provider: Optional[str] = None,
        profile_id: Optional[UUID] = None,
        allowed_providers: Optional[list[str]] = None,
        preferred_provider: Optional[str] = None,
    ) -> Optional[UserApiKey]:
        normalized_allowed = [item.strip().lower() for item in (allowed_providers or []) if item and item.strip()]
        fallback_provider = (preferred_provider or provider or settings.llm_provider).strip().lower()
        candidates = [
            ("user", UserApiKey.user_id == user_id),
        ]
        if profile_id:
            profile_token = str(profile_id)
            candidates.append(
                (
                    "profile",
                    (UserApiKey.profile_id == profile_id) | UserApiKey.profile_ids.contains([profile_token]),
                )
            )
        candidates.append(("platform", UserApiKey.user_id.is_(None)))

        for owner_type, id_filter in candidates:
            query = select(UserApiKey).where(
                UserApiKey.owner_type == owner_type,
                id_filter,
                UserApiKey.is_active == True,
            )
            if normalized_allowed:
                query = query.where(UserApiKey.provider.in_(normalized_allowed))
            elif provider:
                query = query.where(UserApiKey.provider == provider)

            result = await db.execute(query.order_by(UserApiKey.created_at.desc()))
            key_rows = result.scalars().all()
            if not key_rows:
                continue

            preferred_match = next((row for row in key_rows if row.provider == fallback_provider), None)
            if preferred_match:
                return preferred_match
            return key_rows[0]
        return None

    async def resolve(
        self,
        db: AsyncSession,
        user_id: UUID,
        provider: Optional[str] = None,
        profile_id: Optional[UUID] = None,
        allowed_providers: Optional[list[str]] = None,
        preferred_provider: Optional[str] = None,
    ) -> Optional[str]:
        key_obj = await self.resolve_key(
            db,
            user_id,
            provider,
            profile_id,
            allowed_providers=allowed_providers,
            preferred_provider=preferred_provider,
        )
        if key_obj:
            return self.decrypt(key_obj)
        return None


api_key_resolver = ApiKeyResolver()
