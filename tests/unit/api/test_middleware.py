"""Tests for API middleware: correlation ID, tenant required, response headers."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_correlation_id_generated(client: AsyncClient):
    """When X-Correlation-ID is not sent, response has a generated correlation ID."""
    r = await client.get("/health", headers={"X-Tenant-ID": "t1"})
    assert r.status_code == 200
    assert "X-Correlation-ID" in r.headers
    assert len(r.headers["X-Correlation-ID"]) > 0


@pytest.mark.asyncio
async def test_correlation_id_preserved_when_passed(client: AsyncClient):
    """When X-Correlation-ID is sent, the same value is returned in response."""
    correlation_id = "my-correlation-123"
    r = await client.get(
        "/health",
        headers={"X-Tenant-ID": "t1", "X-Correlation-ID": correlation_id},
    )
    assert r.status_code == 200
    assert r.headers.get("X-Correlation-ID") == correlation_id
    data = r.json()
    assert data.get("correlation_id") == correlation_id


@pytest.mark.asyncio
async def test_tenant_required(client: AsyncClient):
    """When X-Tenant-ID is missing, response is 400."""
    r = await client.get("/health")
    assert r.status_code == 400
    assert "detail" in r.json()


@pytest.mark.asyncio
async def test_response_headers_contain_correlation_id(client: AsyncClient):
    """Response headers include X-Correlation-ID."""
    r = await client.get("/tenant/context", headers={"X-Tenant-ID": "t1"})
    assert r.status_code == 200
    assert "X-Correlation-ID" in r.headers
