"""Redis-based distributed locking. SETNX pattern, TTL, safe release. Prevents duplicate workflow execution across nodes."""

import uuid
from typing import Protocol


class RedisLockBackend(Protocol):
    """Minimal Redis operations for distributed lock. Injected; no global state."""

    async def set_nx_ex(self, key: str, value: str, ttl: int) -> bool: ...
    async def get(self, key: str) -> str | None: ...
    async def delete_if_value(self, key: str, value: str) -> bool: ...


LOCK_PREFIX = "lock:"


class DistributedLock:
    """
    Distributed lock using Redis SET NX EX. Safe in concurrent async environment.
    Use a unique token per acquire so only the holder can release.
    """

    def __init__(
        self, backend: RedisLockBackend, key_prefix: str = LOCK_PREFIX
    ) -> None:
        self._backend = backend
        self._prefix = key_prefix
        self._tokens: dict[str, str] = {}

    def _key(self, key: str) -> str:
        return f"{self._prefix}{key}"

    async def acquire(self, key: str, ttl: int) -> bool:
        """
        Try to acquire the lock. Returns True if acquired, False if already held.
        TTL enforced; lock auto-expires to avoid deadlock.
        """
        full_key = self._key(key)
        token = str(uuid.uuid4())
        acquired = await self._backend.set_nx_ex(full_key, token, ttl)
        if acquired:
            self._tokens[key] = token
        return acquired

    async def release(self, key: str) -> None:
        """Release the lock only if we hold it (atomic compare-and-delete)."""
        full_key = self._key(key)
        token = self._tokens.pop(key, None)
        if token is not None:
            await self._backend.delete_if_value(full_key, token)
