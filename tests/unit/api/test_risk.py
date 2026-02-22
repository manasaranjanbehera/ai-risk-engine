"""Tests for POST /risk: valid payload, validation failure, idempotency."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_risk_valid_payload_returns_200(client: AsyncClient, tenant_headers):
    """POST /risk with valid RiskEventCreateRequest returns 200 and EventResponse."""
    headers = {**tenant_headers, "X-Idempotency-Key": "risk-key-1"}
    body = {
        "tenant_id": "test-tenant",
        "version": "1.0",
        "risk_score": 75.5,
        "category": "fraud",
    }
    r = await client.post("/risk/", json=body, headers=headers)
    assert r.status_code == 200
    data = r.json()
    assert "event_id" in data
    assert data["tenant_id"] == "test-tenant"
    assert data["status"] == "received"


@pytest.mark.asyncio
async def test_risk_validation_failure_returns_422(client: AsyncClient, tenant_headers):
    """POST /risk with invalid risk_score returns 422."""
    headers = {**tenant_headers, "X-Idempotency-Key": "risk-key-422"}
    body = {"tenant_id": "test-tenant", "version": "1.0", "risk_score": -1}
    r = await client.post("/risk/", json=body, headers=headers)
    assert r.status_code == 422
    assert "detail" in r.json()


@pytest.mark.asyncio
async def test_risk_idempotency_returns_cached(client: AsyncClient, tenant_headers):
    """Second POST /risk with same idempotency key returns same response."""
    headers = {**tenant_headers, "X-Idempotency-Key": "risk-key-idem"}
    body = {"tenant_id": "test-tenant", "version": "1.0", "risk_score": 50}
    r1 = await client.post("/risk/", json=body, headers=headers)
    r2 = await client.post("/risk/", json=body, headers=headers)
    assert r1.status_code == 200 and r2.status_code == 200
    assert r1.json()["event_id"] == r2.json()["event_id"]


@pytest.mark.asyncio
async def test_risk_missing_idempotency_key_returns_400(
    client: AsyncClient, tenant_headers
):
    """POST /risk without X-Idempotency-Key returns 400."""
    body = {"tenant_id": "test-tenant", "version": "1.0"}
    r = await client.post("/risk/", json=body, headers=tenant_headers)
    assert r.status_code == 400
