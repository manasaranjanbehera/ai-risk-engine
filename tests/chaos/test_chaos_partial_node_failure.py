"""
Chaos: partial node failure, circuit breaker open state, latency spikes.
System must: fail gracefully, classify failure, maintain audit integrity, preserve idempotency.
"""

import asyncio

import pytest

from app.scalability.circuit_breaker import CircuitBreaker, CircuitState


@pytest.mark.asyncio
async def test_circuit_breaker_open_rejects_calls():
    """When circuit is OPEN, call raises; no execution."""
    cb = CircuitBreaker(failure_threshold=2, recovery_timeout_seconds=60.0)

    async def fail():
        raise ValueError("down")

    for _ in range(2):
        with pytest.raises(ValueError):
            await cb.call(fail)
    assert cb.state == CircuitState.OPEN

    with pytest.raises(RuntimeError, match="OPEN"):
        await cb.call(fail)


@pytest.mark.asyncio
async def test_circuit_breaker_half_open_probe_failure_opens_again():
    """After recovery timeout, one probe allowed; if it fails, circuit opens again."""
    cb = CircuitBreaker(failure_threshold=2, recovery_timeout_seconds=0.05)

    async def fail():
        raise ValueError("down")

    for _ in range(2):
        with pytest.raises(ValueError):
            await cb.call(fail)
    await asyncio.sleep(0.1)
    with pytest.raises(ValueError):
        await cb.call(fail)
    assert cb.state == CircuitState.OPEN


@pytest.mark.asyncio
async def test_circuit_breaker_half_open_probe_success_closes():
    """After recovery timeout, one success closes the circuit."""
    cb = CircuitBreaker(failure_threshold=2, recovery_timeout_seconds=0.05)

    async def fail():
        raise ValueError("down")

    async def ok():
        return 42

    for _ in range(2):
        with pytest.raises(ValueError):
            await cb.call(fail)
    await asyncio.sleep(0.1)
    result = await cb.call(ok)
    assert result == 42
    assert cb.state == CircuitState.CLOSED
