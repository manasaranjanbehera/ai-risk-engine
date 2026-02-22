"""Aggregate system health: DB, Redis, RabbitMQ, workflow backlog, circuit breaker states, node latency. Integrates with observability."""

from typing import Any, Awaitable, Callable


class HealthMonitor:
    """
    Aggregates health checks. All backends injected; no global state.
    Returns dict with status per component and overall.
    """

    def __init__(
        self,
        db_health: Callable[[], Awaitable[dict[str, Any]]] | None = None,
        redis_health: Callable[[], Awaitable[dict[str, Any]]] | None = None,
        rabbitmq_health: Callable[[], Awaitable[dict[str, Any]]] | None = None,
        workflow_backlog: Callable[[], Awaitable[int]] | None = None,
        circuit_breaker_states: Callable[[], dict[str, str]] | None = None,
        node_latency_metrics: Callable[[], dict[str, Any]] | None = None,
    ) -> None:
        self._db = db_health
        self._redis = redis_health
        self._rabbitmq = rabbitmq_health
        self._backlog = workflow_backlog
        self._circuit_states = circuit_breaker_states
        self._latency = node_latency_metrics

    async def system_health(self) -> dict[str, Any]:
        """Return aggregated health: db, redis, rabbitmq, workflow_backlog, circuit_breakers, node_latency."""
        out: dict[str, Any] = {
            "db": {"status": "unknown"},
            "redis": {"status": "unknown"},
            "rabbitmq": {"status": "unknown"},
            "workflow_backlog": None,
            "circuit_breaker_states": {},
            "node_latency_metrics": {},
            "status": "ok",
        }
        if self._db:
            try:
                out["db"] = await self._db()
            except Exception as e:
                out["db"] = {"status": "error", "error": str(e)}
                out["status"] = "degraded"
        if self._redis:
            try:
                out["redis"] = await self._redis()
            except Exception as e:
                out["redis"] = {"status": "error", "error": str(e)}
                out["status"] = "degraded"
        if self._rabbitmq:
            try:
                out["rabbitmq"] = await self._rabbitmq()
            except Exception as e:
                out["rabbitmq"] = {"status": "error", "error": str(e)}
                out["status"] = "degraded"
        if self._backlog:
            try:
                out["workflow_backlog"] = await self._backlog()
            except Exception:
                out["workflow_backlog"] = None
                out["status"] = "degraded"
        if self._circuit_states:
            try:
                out["circuit_breaker_states"] = self._circuit_states()
            except Exception:
                out["circuit_breaker_states"] = {}
        if self._latency:
            try:
                out["node_latency_metrics"] = self._latency()
            except Exception:
                out["node_latency_metrics"] = {}
        return out
