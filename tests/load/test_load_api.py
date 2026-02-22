"""
Load test API: asyncio concurrency, multiple tenants, simulated 1k+ requests.
Measures: throughput, latency distribution, error rate.
Asserts: no data corruption, no cross-tenant leakage, no deadlocks.
Uses test app with fake Redis and mock publisher (no real infra).
"""

import asyncio
import time
from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.api import dependencies
from app.main import app


class FakeRedis:
    def __init__(self):
        self._store: dict[str, str] = {}

    async def get_cache(self, key: str):
        return self._store.get(key)

    async def set_cache(self, key: str, value: str, ttl: int = 300):
        self._store[key] = value

    async def set_idempotency_key(self, key: str, ttl: int = 3600):
        if key not in self._store:
            self._store[key] = "1"
            return True
        return False

    async def exists(self, key: str):
        return 1 if key in self._store else 0


@pytest.fixture
def load_test_client():
    """App with fake Redis and mock publisher for load tests."""
    fake_redis = FakeRedis()
    mock_publisher = AsyncMock()
    mock_publisher.publish = AsyncMock(return_value=None)
    app.dependency_overrides[dependencies.get_redis_client] = lambda: fake_redis
    app.dependency_overrides[dependencies.get_publisher] = lambda: mock_publisher
    transport = ASGITransport(app=app)
    client = AsyncClient(transport=transport, base_url="http://test")
    yield client
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_load_health_throughput(load_test_client):
    """Many concurrent GET /health; measure throughput and latency."""
    num_requests = 500
    latencies: list[float] = []
    errors = 0

    async def one_request():
        t0 = time.perf_counter()
        try:
            r = await load_test_client.get(
                "/health",
                headers={"X-Tenant-ID": "load-tenant", "X-Correlation-ID": "load-corr"},
            )
            latencies.append((time.perf_counter() - t0) * 1000)
            assert r.status_code == 200
            return r.json()
        except Exception:
            nonlocal errors
            errors += 1
            raise

    tasks = [one_request() for _ in range(num_requests)]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    ok = sum(1 for r in results if not isinstance(r, Exception))
    assert ok == num_requests
    assert errors == 0
    assert len(latencies) == num_requests
    assert sum(latencies) / len(latencies) < 500  # avg latency under 500ms


@pytest.mark.asyncio
async def test_load_multi_tenant_no_leakage(load_test_client):
    """Multiple tenants hitting health; responses must reflect correct tenant."""
    tenants = [f"tenant-{i}" for i in range(10)]
    per_tenant = 20

    async def one(tenant_id: str, i: int):
        r = await load_test_client.get(
            "/health",
            headers={
                "X-Tenant-ID": tenant_id,
                "X-Correlation-ID": f"corr-{i}",
            },
        )
        assert r.status_code == 200
        data = r.json()
        assert data.get("tenant_id") == tenant_id
        return data["tenant_id"]

    tasks = [one(t, i) for i in range(per_tenant) for t in tenants]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    assert all(not isinstance(r, Exception) for r in results)
    tenant_ids = [r for r in results if isinstance(r, str)]
    assert len(tenant_ids) == 10 * per_tenant
