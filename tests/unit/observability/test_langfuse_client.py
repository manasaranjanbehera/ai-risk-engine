"""LangfuseClient tests: generation log, cost, metrics."""

import pytest

from app.observability.cost_tracker import CostTracker
from app.observability.langfuse_client import LangfuseClient
from app.observability.metrics import MetricsCollector


@pytest.mark.asyncio
async def test_langfuse_generation_log_recorded():
    """Generation log recorded."""
    client = LangfuseClient()
    await client.log_generation(
        event_id="evt-1",
        tenant_id="t1",
        prompt_version=1,
        model_version="simulated@1",
        input_tokens=100,
        output_tokens=50,
        latency_ms=20.0,
    )
    gens = client.get_generations()
    assert len(gens) == 1
    assert gens[0].event_id == "evt-1"
    assert gens[0].tenant_id == "t1"
    assert gens[0].input_tokens == 100
    assert gens[0].output_tokens == 50
    assert gens[0].latency_ms == 20.0
    assert gens[0].estimated_cost > 0


@pytest.mark.asyncio
async def test_langfuse_cost_computed_with_tracker():
    """Cost computed and recorded when cost_tracker provided."""
    cost_tracker = CostTracker(rate_per_1k_tokens=0.002)
    client = LangfuseClient(cost_tracker=cost_tracker)
    await client.log_generation(
        event_id="evt-1",
        tenant_id="t1",
        prompt_version=1,
        model_version="v1",
        input_tokens=1000,
        output_tokens=500,
        latency_ms=10.0,
    )
    assert cost_tracker.get_tenant_cost("t1") == pytest.approx(0.003, rel=1e-5)
    assert cost_tracker.get_request_cost("evt-1") == pytest.approx(0.003, rel=1e-5)


@pytest.mark.asyncio
async def test_langfuse_metrics_updated():
    """Metrics (model_usage_count, prompt_usage_count) updated when collector provided."""
    metrics = MetricsCollector()
    client = LangfuseClient(metrics_collector=metrics)
    await client.log_generation(
        event_id="e1",
        tenant_id="t1",
        prompt_version=1,
        model_version="v1",
        input_tokens=10,
        output_tokens=5,
        latency_ms=1.0,
    )
    out = metrics.export_metrics()
    assert out["counters"].get("model_usage_count") == 1
    assert out["counters"].get("prompt_usage_count") == 1
