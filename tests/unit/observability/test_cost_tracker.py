"""CostTracker tests: per-tenant accumulation, per-model, reset."""

import pytest

from app.observability.cost_tracker import CostTracker


def test_cost_accumulates_per_tenant():
    """Cost accumulates per tenant."""
    c = CostTracker()
    c.add_cost("t1", 1.0)
    c.add_cost("t1", 2.0)
    c.add_cost("t2", 0.5)
    assert c.get_tenant_cost("t1") == 3.0
    assert c.get_tenant_cost("t2") == 0.5


def test_cost_per_model_tracked():
    """Cost per model version tracked."""
    c = CostTracker()
    c.add_cost("t1", 1.0, model_version="gpt-4")
    c.add_cost("t1", 0.5, model_version="gpt-3.5")
    costs = c.get_model_costs()
    assert costs["gpt-4"] == 1.0
    assert costs["gpt-3.5"] == 0.5


def test_cost_from_tokens_deterministic():
    """add_cost_from_tokens uses deterministic rate."""
    c = CostTracker(rate_per_1k_tokens=0.002)
    cost = c.add_cost_from_tokens("t1", 1000, 500, request_id="r1")
    assert cost == pytest.approx(0.003, rel=1e-5)
    assert c.get_request_cost("r1") == pytest.approx(0.003, rel=1e-5)
    assert c.get_tenant_cost("t1") == pytest.approx(0.003, rel=1e-5)


def test_cost_reset():
    """Reset clears all cost data."""
    c = CostTracker()
    c.add_cost("t1", 1.0)
    c.reset()
    assert c.get_tenant_cost("t1") == 0.0
    assert c.get_cumulative() == 0.0
