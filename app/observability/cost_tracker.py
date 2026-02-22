"""Cost tracking per request, tenant, and model version. Deterministic estimation."""

import threading
from typing import Any


class CostTracker:
    """
    Tracks cost per request, per tenant, per model version. Deterministic:
    e.g. token_count * fixed_rate. Thread-safe.
    """

    def __init__(self, rate_per_1k_tokens: float = 0.002) -> None:
        self._rate_per_1k = rate_per_1k_tokens
        self._lock = threading.Lock()
        # tenant_id -> total cost
        self._tenant_costs: dict[str, float] = {}
        # model_version -> total cost
        self._model_costs: dict[str, float] = {}
        # request_id / event_id -> cost for that request
        self._request_costs: dict[str, float] = {}
        self._cumulative: float = 0.0

    def add_cost(
        self,
        tenant_id: str,
        amount: float,
        *,
        model_version: str | None = None,
        request_id: str | None = None,
    ) -> None:
        """Record cost. Optionally attribute to model and/or request."""
        with self._lock:
            self._cumulative += amount
            self._tenant_costs[tenant_id] = (
                self._tenant_costs.get(tenant_id, 0) + amount
            )
            if model_version:
                self._model_costs[model_version] = (
                    self._model_costs.get(model_version, 0) + amount
                )
            if request_id:
                self._request_costs[request_id] = (
                    self._request_costs.get(request_id, 0) + amount
                )

    def add_cost_from_tokens(
        self,
        tenant_id: str,
        input_tokens: int,
        output_tokens: int,
        *,
        model_version: str | None = None,
        request_id: str | None = None,
    ) -> float:
        """Compute cost from token counts (deterministic) and record it. Returns cost."""
        total = input_tokens + output_tokens
        amount = (total / 1000.0) * self._rate_per_1k
        self.add_cost(
            tenant_id,
            amount,
            model_version=model_version,
            request_id=request_id,
        )
        return amount

    def get_tenant_cost(self, tenant_id: str) -> float:
        """Total cost for a tenant."""
        with self._lock:
            return self._tenant_costs.get(tenant_id, 0.0)

    def get_cumulative(self) -> float:
        with self._lock:
            return self._cumulative

    def get_model_costs(self) -> dict[str, float]:
        with self._lock:
            return dict(self._model_costs)

    def get_request_cost(self, request_id: str) -> float:
        with self._lock:
            return self._request_costs.get(request_id, 0.0)

    def export(self) -> dict[str, Any]:
        with self._lock:
            return {
                "cumulative": self._cumulative,
                "by_tenant": dict(self._tenant_costs),
                "by_model": dict(self._model_costs),
                "by_request": dict(self._request_costs),
            }

    def reset(self) -> None:
        with self._lock:
            self._tenant_costs.clear()
            self._model_costs.clear()
            self._request_costs.clear()
            self._cumulative = 0.0
