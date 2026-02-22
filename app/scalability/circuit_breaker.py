"""Circuit breaker pattern: CLOSED, OPEN, HALF_OPEN. Failure threshold and recovery timeout. Metrics tracking."""

import asyncio
import time
from enum import Enum
from typing import Any, Awaitable, Callable, TypeVar

T = TypeVar("T")


class CircuitState(str, Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreaker:
    """
    Circuit breaker: after failure_threshold failures, open for recovery_timeout_seconds,
    then half-open for one probe. Thread-safe and async-safe via asyncio.Lock.
    """

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout_seconds: float = 30.0,
        name: str = "default",
        metrics_callback: Any = None,
    ) -> None:
        self._threshold = failure_threshold
        self._recovery_timeout = recovery_timeout_seconds
        self._name = name
        self._metrics = metrics_callback
        self._state = CircuitState.CLOSED
        self._failures = 0
        self._last_failure_time: float | None = None
        self._lock = asyncio.Lock()

    @property
    def state(self) -> CircuitState:
        return self._state

    def _record_success(self) -> None:
        self._failures = 0
        self._state = CircuitState.CLOSED
        if self._metrics and hasattr(self._metrics, "increment"):
            self._metrics.increment("circuit_breaker_success", 1, category=self._name)

    def _record_failure(self) -> None:
        self._last_failure_time = time.monotonic()
        self._failures += 1
        if self._metrics and hasattr(self._metrics, "increment"):
            self._metrics.increment("circuit_breaker_failure", 1, category=self._name)
        if self._failures >= self._threshold:
            self._state = CircuitState.OPEN

    async def call(
        self,
        func: Callable[..., Awaitable[T]],
        *args: Any,
        **kwargs: Any,
    ) -> T:
        """Execute func through the circuit. Raises if circuit is OPEN; on failure counts and may open."""
        async with self._lock:
            if self._state == CircuitState.OPEN:
                if self._last_failure_time is not None:
                    if (
                        time.monotonic() - self._last_failure_time
                        >= self._recovery_timeout
                    ):
                        self._state = CircuitState.HALF_OPEN
                    else:
                        raise RuntimeError(f"Circuit breaker {self._name} is OPEN")
                else:
                    raise RuntimeError(f"Circuit breaker {self._name} is OPEN")
            # CLOSED or HALF_OPEN: try the call
        try:
            result = await func(*args, **kwargs)
            async with self._lock:
                self._record_success()
            return result
        except Exception:
            async with self._lock:
                self._record_failure()
                if self._state == CircuitState.HALF_OPEN:
                    self._state = CircuitState.OPEN
            raise
