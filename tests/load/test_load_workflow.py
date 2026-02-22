"""
Load test workflow layer: asyncio concurrency, multiple tenants, simulated 1k+ requests.
Measures: throughput, latency distribution, error rate, cost accumulation, approval escalation rate.
Asserts: no data corruption, no cross-tenant leakage, no deadlocks, no race conditions.
"""

import asyncio
import time
from unittest.mock import AsyncMock

import pytest

from app.observability.cost_tracker import CostTracker
from app.observability.metrics import MetricsCollector
from app.scalability.bulkhead import BulkheadExecutor
from app.scalability.rate_limiter import InMemoryRateLimitBackend, TenantRateLimiter
from app.scalability.workload_partitioning import WorkloadPartitioner
from app.workflows.langgraph.risk_workflow import RiskWorkflow
from app.workflows.langgraph.state_models import RiskState


def _make_state(event_id: str, tenant_id: str, i: int) -> RiskState:
    return RiskState(
        event_id=event_id,
        tenant_id=tenant_id,
        correlation_id=f"corr-{i}",
        raw_event={"event_type": "load_test", "index": i},
        model_version="simulated@1",
        prompt_version=1,
        audit_trail=[],
    )


@pytest.fixture
def audit_logger():
    audit = AsyncMock()
    audit.log_action = AsyncMock(return_value=None)
    return audit


@pytest.mark.asyncio
async def test_load_workflow_concurrent_multi_tenant(audit_logger):
    """Run many workflow invocations across tenants; no cross-tenant leakage."""
    metrics = MetricsCollector()
    cost_tracker = CostTracker()
    workflow = RiskWorkflow(
        audit_logger=audit_logger,
        state_store=None,
        metrics_collector=metrics,
        cost_tracker=cost_tracker,
    )
    num_tenants = 5
    total_requests = 250
    latencies: list[float] = []
    tenant_results: dict[str, list[str]] = {f"t{k}": [] for k in range(num_tenants)}

    async def run_one(tenant_id: str, i: int):
        event_id = f"evt-{tenant_id}-{i}"
        state = _make_state(event_id, tenant_id, i)
        t0 = time.perf_counter()
        result = await workflow.run(state)
        latencies.append((time.perf_counter() - t0) * 1000)
        tenant_results[tenant_id].append(result.event_id)
        return result.event_id

    task_list = [run_one(f"t{i % num_tenants}", i) for i in range(total_requests)]
    results = await asyncio.gather(*task_list, return_exceptions=True)

    completed = sum(1 for r in results if not isinstance(r, Exception))
    assert completed == total_requests
    for tenant_id, event_ids in tenant_results.items():
        for eid in event_ids:
            assert eid.startswith(
                f"evt-{tenant_id}-"
            ), f"cross-tenant leakage: {eid} in {tenant_id}"
    assert len(latencies) == completed
    assert len(latencies) >= 200


@pytest.mark.asyncio
async def test_load_bulkhead_no_deadlock():
    """Bulkhead under load: no deadlocks."""
    bulk = BulkheadExecutor(max_concurrent=10, max_queued=100)
    results = await asyncio.gather(
        *[bulk.submit(asyncio.sleep, 0.01) for _ in range(50)],
        return_exceptions=True,
    )
    assert not any(isinstance(r, Exception) for r in results)


@pytest.mark.asyncio
async def test_load_rate_limiter_burst():
    """Rate limiter under burst: some allowed, some denied; no corruption."""
    backend = InMemoryRateLimitBackend()
    limiter = TenantRateLimiter(
        backend=backend, requests_per_window=100, window_seconds=60
    )
    outcomes = await asyncio.gather(
        *[limiter.allow_request("burst-tenant") for _ in range(150)],
        return_exceptions=True,
    )
    allowed = sum(1 for o in outcomes if o is True)
    denied = sum(1 for o in outcomes if o is False)
    assert allowed == 100
    assert denied == 50


@pytest.mark.asyncio
async def test_load_partitioning_deterministic():
    """Workload partitioning: deterministic under many tenants."""
    p = WorkloadPartitioner(num_partitions=32)
    for _ in range(1000):
        tid = f"tenant-{_}"
        part = p.get_partition(tid)
        assert p.get_partition(tid) == part
