"""Fixtures for API unit tests: in-memory Redis, mock publisher, AsyncClient."""

from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


class FakeRedis:
    """In-memory Redis for unit tests."""

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
def fake_redis():
    return FakeRedis()


@pytest.fixture
def mock_publisher():
    """Mock RabbitMQ publisher so tests do not connect to real broker."""
    p = AsyncMock()
    p.publish = AsyncMock(return_value=None)
    return p


@pytest.fixture
def app_with_overrides(fake_redis, mock_publisher):
    """App with Redis and publisher overridden for testing."""
    from app.api import dependencies

    app.dependency_overrides[dependencies.get_redis_client] = lambda: fake_redis
    app.dependency_overrides[dependencies.get_publisher] = lambda: mock_publisher
    yield app
    app.dependency_overrides.clear()


@pytest.fixture
async def client(app_with_overrides):
    """Async HTTP client for testing; uses overridden app (all API tests use this)."""
    transport = ASGITransport(app=app_with_overrides)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
def tenant_headers():
    return {"X-Tenant-ID": "test-tenant"}
