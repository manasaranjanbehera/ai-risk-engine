"""Tests for GET /tenant/context: valid header returns tenant; missing returns 400."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_tenant_context_valid_header_returns_tenant(client: AsyncClient):
    """GET /tenant/context with X-Tenant-ID returns tenant_id and correlation_id."""
    r = await client.get(
        "/tenant/context",
        headers={"X-Tenant-ID": "my-tenant", "X-Correlation-ID": "corr-1"},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["tenant_id"] == "my-tenant"
    assert data["correlation_id"] == "corr-1"


@pytest.mark.asyncio
async def test_tenant_context_missing_header_returns_400(client: AsyncClient):
    """GET /tenant/context without X-Tenant-ID returns 400."""
    r = await client.get("/tenant/context")
    assert r.status_code == 400
    assert "detail" in r.json()
