"""Tests for events API: idempotency, validation, missing idempotency header."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_events_idempotency_first_call_stores(
    client: AsyncClient, tenant_headers
):
    """First POST /events with idempotency key creates event and returns 200."""
    headers = {**tenant_headers, "X-Idempotency-Key": "key-1"}
    body = {
        "tenant_id": "test-tenant",
        "version": "1.0",
        "risk_score": 50,
    }
    r = await client.post("/events/", json=body, headers=headers)
    assert r.status_code == 200
    data = r.json()
    assert "event_id" in data
    assert data["tenant_id"] == "test-tenant"
    assert data["status"] == "received"


@pytest.mark.asyncio
async def test_events_idempotency_second_call_returns_cached(
    client: AsyncClient, tenant_headers
):
    """Second POST /events with same idempotency key returns cached response."""
    headers = {**tenant_headers, "X-Idempotency-Key": "key-2"}
    body = {"tenant_id": "test-tenant", "version": "1.0"}
    r1 = await client.post("/events/", json=body, headers=headers)
    assert r1.status_code == 200
    first_event_id = r1.json()["event_id"]
    r2 = await client.post("/events/", json=body, headers=headers)
    assert r2.status_code == 200
    assert r2.json()["event_id"] == first_event_id


@pytest.mark.asyncio
async def test_events_validation_error_returns_422(client: AsyncClient, tenant_headers):
    """Invalid payload (e.g. empty version) returns 422."""
    headers = {**tenant_headers, "X-Idempotency-Key": "key-422"}
    body = {"tenant_id": "test-tenant", "version": ""}
    r = await client.post("/events/", json=body, headers=headers)
    assert r.status_code == 422
    assert "detail" in r.json()


@pytest.mark.asyncio
async def test_events_missing_idempotency_header_returns_400(
    client: AsyncClient, tenant_headers
):
    """POST /events without X-Idempotency-Key returns 400."""
    body = {"tenant_id": "test-tenant", "version": "1.0"}
    r = await client.post("/events/", json=body, headers=tenant_headers)
    assert r.status_code == 400
    assert "detail" in r.json()


@pytest.mark.asyncio
async def test_events_get_not_found_returns_404(client: AsyncClient, tenant_headers):
    """GET /events/{event_id} with non-existent id returns 404."""
    r = await client.get(
        "/events/00000000-0000-0000-0000-000000000000", headers=tenant_headers
    )
    assert r.status_code == 404
    assert "detail" in r.json()


@pytest.mark.asyncio
async def test_events_get_by_id(client: AsyncClient, tenant_headers):
    """GET /events/{event_id} returns event after create."""
    key = "key-get"
    headers = {**tenant_headers, "X-Idempotency-Key": key}
    body = {"tenant_id": "test-tenant", "version": "1.0", "risk_score": 10}
    create_r = await client.post("/events/", json=body, headers=headers)
    assert create_r.status_code == 200
    event_id = create_r.json()["event_id"]
    get_r = await client.get(f"/events/{event_id}", headers=tenant_headers)
    assert get_r.status_code == 200
    assert get_r.json()["event_id"] == event_id
