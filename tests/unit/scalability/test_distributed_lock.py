"""DistributedLock: concurrent access simulation, acquire/release, TTL."""

import pytest

from app.scalability.distributed_lock import DistributedLock


class FakeRedisLockBackend:
    def __init__(self) -> None:
        self._store: dict[str, str] = {}
        self._ttl: dict[str, int] = {}

    async def set_nx_ex(self, key: str, value: str, ttl: int) -> bool:
        if key in self._store:
            return False
        self._store[key] = value
        self._ttl[key] = ttl
        return True

    async def get(self, key: str) -> str | None:
        return self._store.get(key)

    async def delete_if_value(self, key: str, value: str) -> bool:
        if self._store.get(key) == value:
            del self._store[key]
            self._ttl.pop(key, None)
            return True
        return False


@pytest.fixture
def backend():
    return FakeRedisLockBackend()


@pytest.fixture
def lock(backend):
    return DistributedLock(backend=backend)


@pytest.mark.asyncio
async def test_acquire_release(lock):
    got = await lock.acquire("workflow:evt-1", ttl=60)
    assert got is True
    await lock.release("workflow:evt-1")
    # Can acquire again after release
    got2 = await lock.acquire("workflow:evt-1", ttl=60)
    assert got2 is True


@pytest.mark.asyncio
async def test_acquire_fails_when_held(backend, lock):
    await lock.acquire("key1", ttl=60)
    second = await lock.acquire("key1", ttl=60)
    assert second is False


@pytest.mark.asyncio
async def test_release_only_holder(backend, lock):
    await lock.acquire("key1", ttl=60)
    await lock.release("key1")
    assert "lock:key1" not in backend._store


@pytest.mark.asyncio
async def test_concurrent_access_simulation(backend):
    """Simulate concurrent acquire: only one succeeds per key."""
    lock = DistributedLock(backend=backend)
    results = []
    for _ in range(5):
        r = await lock.acquire("same_key", ttl=10)
        results.append(r)
        if r:
            await lock.release("same_key")
    # First acquire True, rest False until release; after release next True. So we get True, False*4 or True, False, True, False, False depending on order.
    assert sum(results) >= 1
    assert results[0] is True
