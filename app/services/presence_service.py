from __future__ import annotations

import asyncio
from collections import Counter
from uuid import UUID

import redis.asyncio as aioredis

from app.core.config import settings


class PresenceService:
    """Redis-backed presence with TTL; memory is only a development fallback."""

    _TTL_SECONDS = 90

    def __init__(self) -> None:
        self._active_connections: Counter[str] = Counter()
        self._lock = asyncio.Lock()
        self._redis = aioredis.from_url(settings.redis_url, decode_responses=True)

    @staticmethod
    def _key(user_id: UUID | str) -> str:
        return f"presence:user:{user_id}"

    async def connect(self, user_id: UUID | str) -> None:
        try:
            async with self._redis.pipeline(transaction=True) as pipe:
                pipe.incr(self._key(user_id))
                pipe.expire(self._key(user_id), self._TTL_SECONDS)
                await pipe.execute()
            return
        except Exception:
            if settings.environment.lower() == "production":
                raise
        async with self._lock:
            self._active_connections[str(user_id)] += 1

    async def heartbeat(self, user_id: UUID | str) -> None:
        try:
            await self._redis.expire(self._key(user_id), self._TTL_SECONDS)
        except Exception:
            if settings.environment.lower() == "production":
                raise

    async def disconnect(self, user_id: UUID | str) -> None:
        try:
            await self._redis.eval(
                """
                local value = tonumber(redis.call('GET', KEYS[1]) or '0')
                if value <= 1 then
                    return redis.call('DEL', KEYS[1])
                end
                redis.call('DECR', KEYS[1])
                return redis.call('EXPIRE', KEYS[1], ARGV[1])
                """,
                1,
                self._key(user_id),
                self._TTL_SECONDS,
            )
            return
        except Exception:
            if settings.environment.lower() == "production":
                raise
        async with self._lock:
            key = str(user_id)
            if key not in self._active_connections:
                return
            self._active_connections[key] -= 1
            if self._active_connections[key] <= 0:
                self._active_connections.pop(key, None)

    async def get_active_user_ids(self) -> list[str]:
        try:
            user_ids = []
            async for key in self._redis.scan_iter(match="presence:user:*", count=200):
                user_ids.append(key.removeprefix("presence:user:"))
            return user_ids
        except Exception:
            if settings.environment.lower() == "production":
                raise
        async with self._lock:
            return list(self._active_connections.keys())

    async def is_online(self, user_id: UUID | str) -> bool:
        try:
            return bool(await self._redis.exists(self._key(user_id)))
        except Exception:
            if settings.environment.lower() == "production":
                raise
        async with self._lock:
            return self._active_connections.get(str(user_id), 0) > 0


presence_service = PresenceService()
