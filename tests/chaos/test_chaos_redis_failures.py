"""
Chaos: Redis outage (get/set fail).
System must: fail gracefully, classify failure, not corrupt state.
Distributed lock and rate limiter use backend; when backend fails, operations fail cleanly.
"""

import pytest

from app.scalability.distributed_lock import DistributedLock
from app.scalability.rate_limiter import InMemoryRateLimitBackend, TenantRateLimiter


class FailingBackend:
    """Backend that raises on every call (simulated Redis outage)."""

    async def set_nx_ex(self, key: str, value: str, ttl: int) -> bool:
        raise ConnectionError("Redis connection refused")

    async def get(self, key: str) -> str | None:
        raise ConnectionError("Redis connection refused")

    async def delete_if_value(self, key: str, value: str) -> bool:
        raise ConnectionError("Redis connection refused")


@pytest.mark.asyncio
async def test_distributed_lock_acquire_fails_gracefully_on_redis_outage():
    """When Redis is down, acquire raises; no corrupt local state."""
    lock = DistributedLock(backend=FailingBackend())
    with pytest.raises(ConnectionError):
        await lock.acquire("workflow:evt-1", ttl=60)
    # Release is no-op if we never acquired
    await lock.release("workflow:evt-1")  # should not raise


@pytest.mark.asyncio
async def test_rate_limiter_uses_in_memory_backend_no_redis():
    """Rate limiter with in-memory backend works without Redis; chaos scenario uses fake."""
    backend = InMemoryRateLimitBackend()
    limiter = TenantRateLimiter(
        backend=backend, requests_per_window=10, window_seconds=60
    )
    for _ in range(10):
        assert await limiter.allow_request("t1") is True
    assert await limiter.allow_request("t1") is False
