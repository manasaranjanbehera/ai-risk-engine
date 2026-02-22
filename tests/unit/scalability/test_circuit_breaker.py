"""CircuitBreaker: state transitions CLOSED -> OPEN -> HALF_OPEN."""

import asyncio

import pytest

from app.scalability.circuit_breaker import CircuitBreaker, CircuitState


@pytest.mark.asyncio
async def test_closed_success():
    cb = CircuitBreaker(failure_threshold=3, recovery_timeout_seconds=0.1)

    async def ok():
        return 42

    result = await cb.call(ok)
    assert result == 42
    assert cb.state == CircuitState.CLOSED


@pytest.mark.asyncio
async def test_opens_after_threshold():
    cb = CircuitBreaker(failure_threshold=3, recovery_timeout_seconds=10.0)

    async def fail():
        raise ValueError("fail")

    for _ in range(3):
        with pytest.raises(ValueError):
            await cb.call(fail)
    assert cb.state == CircuitState.OPEN

    with pytest.raises(RuntimeError, match="OPEN"):
        await cb.call(fail)


@pytest.mark.asyncio
async def test_half_open_after_recovery():
    cb = CircuitBreaker(failure_threshold=2, recovery_timeout_seconds=0.05)

    async def fail():
        raise ValueError("fail")

    for _ in range(2):
        with pytest.raises(ValueError):
            await cb.call(fail)
    assert cb.state == CircuitState.OPEN

    await asyncio.sleep(0.1)

    async def ok():
        return 1

    result = await cb.call(ok)
    assert result == 1
    assert cb.state == CircuitState.CLOSED


@pytest.mark.asyncio
async def test_half_open_failure_opens_again():
    cb = CircuitBreaker(failure_threshold=2, recovery_timeout_seconds=0.05)

    async def fail():
        raise ValueError("fail")

    for _ in range(2):
        with pytest.raises(ValueError):
            await cb.call(fail)
    await asyncio.sleep(0.1)
    with pytest.raises(ValueError):
        await cb.call(fail)
    assert cb.state == CircuitState.OPEN
