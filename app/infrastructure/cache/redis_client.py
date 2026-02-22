# app/infrastructure/cache/redis_client.py

import redis.asyncio as redis

from app.config.settings import settings


class RedisClient:
    def __init__(self):
        self.client = redis.from_url(
            settings.redis_url,
            decode_responses=True,
        )

    async def set_idempotency_key(self, key: str, ttl: int = 3600):
        return await self.client.set(key, "1", ex=ttl, nx=True)

    async def exists(self, key: str):
        return await self.client.exists(key)

    async def set_cache(self, key: str, value: str, ttl: int = 300):
        await self.client.set(key, value, ex=ttl)

    async def get_cache(self, key: str):
        return await self.client.get(key)

    async def rate_limit(
        self,
        key: str,
        limit: int,
        window: int,
    ):
        current = await self.client.incr(key)
        if current == 1:
            await self.client.expire(key, window)

        return current <= limit

    async def set_nx_ex(self, key: str, value: str, ttl: int) -> bool:
        """Set key to value only if not exists, with TTL. Returns True if key was set."""
        return bool(await self.client.set(key, value, nx=True, ex=ttl))

    async def get(self, key: str) -> str | None:
        """Get value for key. Returns None if key does not exist."""
        return await self.client.get(key)

    async def delete_key(self, key: str) -> None:
        """Delete a key."""
        await self.client.delete(key)

    async def delete_if_value(self, key: str, value: str) -> bool:
        """Delete key only if its value equals value (atomic). Returns True if deleted."""
        script = "if redis.call('get', KEYS[1]) == ARGV[1] then return redis.call('del', KEYS[1]) else return 0 end"
        result = await self.client.eval(script, 1, key, value)
        return bool(result)

    async def incr(self, key: str) -> int:
        """Increment key, return new value."""
        return await self.client.incr(key)

    async def expire(self, key: str, seconds: int) -> None:
        """Set TTL on key."""
        await self.client.expire(key, seconds)
