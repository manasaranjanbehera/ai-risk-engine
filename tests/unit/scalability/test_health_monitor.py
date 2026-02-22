"""HealthMonitor: aggregate db, redis, rabbitmq, backlog, circuit breakers, latency."""

import pytest

from app.scalability.health_monitor import HealthMonitor


@pytest.mark.asyncio
async def test_system_health_empty():
    monitor = HealthMonitor()
    out = await monitor.system_health()
    assert "db" in out and out["db"]["status"] == "unknown"
    assert "redis" in out and out["redis"]["status"] == "unknown"
    assert "status" in out and out["status"] == "ok"


@pytest.mark.asyncio
async def test_system_health_with_checks():
    async def db_ok():
        return {"status": "ok"}

    async def redis_ok():
        return {"status": "ok"}

    monitor = HealthMonitor(db_health=db_ok, redis_health=redis_ok)
    out = await monitor.system_health()
    assert out["db"]["status"] == "ok"
    assert out["redis"]["status"] == "ok"


@pytest.mark.asyncio
async def test_system_health_degraded_on_error():
    async def db_fail():
        raise RuntimeError("connection refused")

    monitor = HealthMonitor(db_health=db_fail)
    out = await monitor.system_health()
    assert out["db"]["status"] == "error"
    assert out["status"] == "degraded"


@pytest.mark.asyncio
async def test_workflow_backlog_and_circuit_states():
    async def backlog():
        return 5

    def circuits():
        return {"publisher": "closed"}

    monitor = HealthMonitor(workflow_backlog=backlog, circuit_breaker_states=circuits)
    out = await monitor.system_health()
    assert out["workflow_backlog"] == 5
    assert out["circuit_breaker_states"] == {"publisher": "closed"}
