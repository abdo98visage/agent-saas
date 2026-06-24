from __future__ import annotations

import asyncio
from collections import Counter
from uuid import UUID


class PresenceService:
    def __init__(self) -> None:
        self._active_connections: Counter[str] = Counter()
        self._lock = asyncio.Lock()

    async def connect(self, user_id: UUID | str) -> None:
        async with self._lock:
            self._active_connections[str(user_id)] += 1

    async def disconnect(self, user_id: UUID | str) -> None:
        async with self._lock:
            key = str(user_id)
            if key not in self._active_connections:
                return
            self._active_connections[key] -= 1
            if self._active_connections[key] <= 0:
                self._active_connections.pop(key, None)

    async def get_active_user_ids(self) -> list[str]:
        async with self._lock:
            return list(self._active_connections.keys())

    async def is_online(self, user_id: UUID | str) -> bool:
        async with self._lock:
            return self._active_connections.get(str(user_id), 0) > 0


presence_service = PresenceService()
