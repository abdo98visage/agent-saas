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
        provider: str,
        profile_id: Optional[UUID] = None,
    ) -> Optional[UserApiKey]:
        candidates = [
            (UserApiKey.owner_type == "user", UserApiKey.user_id == user_id),
        ]
        if profile_id:
            candidates.append((UserApiKey.owner_type == "profile", UserApiKey.profile_id == profile_id))
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
            key_obj = result.scalar_one_or_none()
            if key_obj:
                return key_obj
        return None

    async def resolve(
        self,
        db: AsyncSession,
        user_id: UUID,
        provider: str,
        profile_id: Optional[UUID] = None,
    ) -> Optional[str]:
        key_obj = await self.resolve_key(db, user_id, provider, profile_id)
        if key_obj:
            return self.decrypt(key_obj)
        return None


api_key_resolver = ApiKeyResolver()
