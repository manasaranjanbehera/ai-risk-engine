"""Simulated Langfuse-style client for LLM trace logging. No external calls."""

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.observability.cost_tracker import CostTracker
    from app.observability.metrics import MetricsCollector


@dataclass
class GenerationRecord:
    """Single generation log entry (in-memory)."""

    event_id: str
    tenant_id: str
    prompt_version: int
    model_version: str
    input_tokens: int
    output_tokens: int
    estimated_cost: float
    latency_ms: float


class LangfuseClient:
    """
    Simulated Langfuse client. log_generation records prompt/model version,
    tokens, cost, latency, tenant_id, event_id. Integrates with CostTracker
    and MetricsCollector (injected); no external calls.
    """

    def __init__(
        self,
        cost_tracker: "CostTracker | None" = None,
        metrics_collector: "MetricsCollector | None" = None,
    ) -> None:
        self._cost_tracker = cost_tracker
        self._metrics = metrics_collector
        self._generations: list[GenerationRecord] = []

    async def log_generation(
        self,
        *,
        event_id: str,
        tenant_id: str,
        prompt_version: int,
        model_version: str,
        input_tokens: int,
        output_tokens: int,
        latency_ms: float,
        cost_tracker: "CostTracker | None" = None,
    ) -> float:
        """
        Log a generation. Computes estimated_cost via cost_tracker (or instance).
        Updates metrics (model_usage_count, prompt_usage_count). Returns estimated cost.
        """
        ct = cost_tracker or self._cost_tracker
        cost = 0.0
        if ct:
            cost = ct.add_cost_from_tokens(
                tenant_id,
                input_tokens,
                output_tokens,
                model_version=model_version,
                request_id=event_id,
            )
        else:
            # No tracker: deterministic estimate (e.g. 0.002 per 1k tokens)
            total = input_tokens + output_tokens
            cost = (total / 1000.0) * 0.002

        record = GenerationRecord(
            event_id=event_id,
            tenant_id=tenant_id,
            prompt_version=prompt_version,
            model_version=model_version,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            estimated_cost=cost,
            latency_ms=latency_ms,
        )
        self._generations.append(record)

        if self._metrics:
            self._metrics.increment("model_usage_count")
            self._metrics.increment("prompt_usage_count")

        return cost

    def get_generations(self) -> list[GenerationRecord]:
        """Return all logged generations (for tests)."""
        return list(self._generations)

    def reset(self) -> None:
        """Clear stored generations (for tests)."""
        self._generations.clear()
