"""Tests for GET /health: 200, tenant required, correlation ID in response."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health_returns_200_with_tenant(client: AsyncClient):
    """GET /health with X-Tenant-ID returns 200."""
    r = await client.get("/health", headers={"X-Tenant-ID": "t1"})
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "ok"
    assert "tenant_id" in data
    assert "correlation_id" in data


@pytest.mark.asyncio
async def test_health_tenant_header_required(client: AsyncClient):
    """GET /health without X-Tenant-ID returns 400."""
    r = await client.get("/health")
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_health_correlation_id_auto_generated(client: AsyncClient):
    """GET /health returns a correlation_id when not provided."""
    r = await client.get("/health", headers={"X-Tenant-ID": "t1"})
    assert r.status_code == 200
    assert "correlation_id" in r.json()
    assert len(r.json()["correlation_id"]) > 0
