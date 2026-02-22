"""TenantRateLimiter: per-tenant limit, burst handling, metrics."""

import pytest

from app.scalability.rate_limiter import InMemoryRateLimitBackend, TenantRateLimiter


@pytest.fixture
def backend():
    return InMemoryRateLimitBackend()


@pytest.fixture
def limiter(backend):
    return TenantRateLimiter(backend=backend, requests_per_window=3, window_seconds=60)


@pytest.mark.asyncio
async def test_allow_under_limit(limiter):
    assert await limiter.allow_request("t1") is True
    assert await limiter.allow_request("t1") is True
    assert await limiter.allow_request("t1") is True


@pytest.mark.asyncio
async def test_deny_over_limit(limiter):
    for _ in range(3):
        await limiter.allow_request("t1")
    assert await limiter.allow_request("t1") is False


@pytest.mark.asyncio
async def test_per_tenant(limiter):
    for _ in range(3):
        await limiter.allow_request("t1")
    assert await limiter.allow_request("t2") is True


@pytest.mark.asyncio
async def test_burst_handling(backend):
    limiter = TenantRateLimiter(
        backend=backend, requests_per_window=5, window_seconds=60
    )
    for _ in range(5):
        assert await limiter.allow_request("burst-tenant") is True
    assert await limiter.allow_request("burst-tenant") is False
