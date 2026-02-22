"""Per-tenant token-bucket / sliding-window rate limiter. Metrics-integrated."""

import time
from typing import Any, Protocol


class RateLimitBackend(Protocol):
    """Backend for rate limit state (e.g. Redis). Injected."""

    async def incr_window(self, key: str, window_seconds: int) -> int: ...
    async def get_current_count(self, key: str) -> int: ...


class InMemoryRateLimitBackend:
    """In-memory sliding window: key -> list of timestamps. For tests or single-node."""

    def __init__(self) -> None:
        self._windows: dict[str, list[float]] = {}
        self._lock = (
            None  # optional asyncio lock if needed; single-thread async is safe
        )

    async def incr_window(self, key: str, window_seconds: int) -> int:
        now = time.monotonic()
        cutoff = now - window_seconds
        if key not in self._windows:
            self._windows[key] = []
        self._windows[key] = [t for t in self._windows[key] if t > cutoff]
        self._windows[key].append(now)
        return len(self._windows[key])

    async def get_current_count(self, key: str) -> int:
        return len(self._windows.get(key, []))


class TenantRateLimiter:
    """
    Per-tenant rate limiter. Sliding window; optional metrics callback.
    """

    def __init__(
        self,
        backend: RateLimitBackend,
        requests_per_window: int = 100,
        window_seconds: int = 60,
        metrics_callback: Any = None,
    ) -> None:
        self._backend = backend
        self._limit = requests_per_window
        self._window = window_seconds
        self._metrics = metrics_callback
        self._key_prefix = "rate:tenant:"

    def _key(self, tenant_id: str) -> str:
        return f"{self._key_prefix}{tenant_id}"

    async def allow_request(self, tenant_id: str) -> bool:
        """
        Check if request is allowed for tenant. Returns True if under limit.
        Records metric if metrics_callback provided (e.g. rate_limit_hits).
        """
        key = self._key(tenant_id)
        # Sliding window: we need current count in window; backend can use incr + window
        count = await self._backend.incr_window(key, self._window)
        allowed = count <= self._limit
        if self._metrics and not allowed:
            if callable(self._metrics):
                self._metrics("rate_limit_exceeded", tenant_id=tenant_id)
            elif hasattr(self._metrics, "increment"):
                self._metrics.increment("rate_limit_exceeded", 1, tenant_id=tenant_id)
        return allowed
