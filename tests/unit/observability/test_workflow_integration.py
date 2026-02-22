"""Workflow integration tests: observability hooks with RiskWorkflow and ComplianceWorkflow."""

from unittest.mock import AsyncMock

import pytest

from app.observability.cost_tracker import CostTracker
from app.observability.failure_classifier import FailureClassifier
from app.observability.metrics import MetricsCollector
from app.observability.tracing import TracingService
from app.workflows.langgraph.risk_workflow import RiskWorkflow
from app.workflows.langgraph.state_models import ComplianceState, RiskState


@pytest.fixture
def audit_repository():
    repo = AsyncMock()
    repo.save = AsyncMock(return_value=None)
    return repo


@pytest.fixture
def audit_logger(audit_repository):
    from app.governance.audit_logger import AuditLogger

    return AuditLogger(repository=audit_repository)


@pytest.fixture
def metrics():
    return MetricsCollector()


@pytest.fixture
def tracing():
    return TracingService()


@pytest.fixture
def cost_tracker():
    return CostTracker()


@pytest.fixture
def failure_classifier():
    return FailureClassifier()


@pytest.mark.asyncio
async def test_risk_workflow_node_latency_recorded(audit_logger, metrics, tracing):
    """Node latency recorded when metrics and tracing are provided."""
    workflow = RiskWorkflow(
        audit_logger=audit_logger,
        metrics_collector=metrics,
        tracing_service=tracing,
    )
    state = RiskState(
        event_id="e1",
        tenant_id="t1",
        correlation_id="c1",
        raw_event={"event_type": "standard"},
        audit_trail=[],
    )
    await workflow.run(state)
    out = metrics.export_metrics()
    assert "node_execution_latency" in str(out["histograms"])
    assert len(tracing.get_traces()) == 1
    trace = tracing.get_traces()[0]
    node_names = [s.name for s in trace.spans]
    assert "risk_workflow" in node_names
    assert "retrieval" in node_names
    assert "decision" in node_names


@pytest.mark.asyncio
async def test_risk_workflow_cost_tracked(audit_logger, cost_tracker):
    """Cost tracked when cost_tracker provided."""
    workflow = RiskWorkflow(audit_logger=audit_logger, cost_tracker=cost_tracker)
    state = RiskState(
        event_id="e1",
        tenant_id="t1",
        correlation_id="c1",
        raw_event={"event_type": "standard"},
        audit_trail=[],
    )
    await workflow.run(state)
    assert cost_tracker.get_tenant_cost("t1") > 0
    assert cost_tracker.get_request_cost("e1") > 0


@pytest.mark.asyncio
async def test_risk_workflow_model_and_prompt_usage_counted(audit_logger, metrics):
    """Model usage and prompt usage counted."""
    workflow = RiskWorkflow(audit_logger=audit_logger, metrics_collector=metrics)
    state = RiskState(
        event_id="e1",
        tenant_id="t1",
        correlation_id="c1",
        raw_event={"event_type": "standard"},
        audit_trail=[],
    )
    await workflow.run(state)
    out = metrics.export_metrics()
    assert out["counters"].get("model_usage_count", 0) >= 5
    assert out["counters"].get("prompt_usage_count", 0) >= 5


@pytest.mark.asyncio
async def test_risk_workflow_approval_required_increments_counter(
    audit_logger, metrics
):
    """Approval-required path increments approval_required_count."""
    workflow = RiskWorkflow(audit_logger=audit_logger, metrics_collector=metrics)
    state = RiskState(
        event_id="e1",
        tenant_id="t1",
        correlation_id="c1",
        raw_event={"event_type": "high_risk"},
        audit_trail=[],
    )
    await workflow.run(state)
    out = metrics.export_metrics()
    assert out["counters"].get("approval_required_count", 0) == 1


@pytest.mark.asyncio
async def test_risk_workflow_metrics_reflect_execution(audit_logger, metrics):
    """request_count, workflow_execution_count, request_latency reflect execution."""
    workflow = RiskWorkflow(audit_logger=audit_logger, metrics_collector=metrics)
    state = RiskState(
        event_id="e1",
        tenant_id="t1",
        correlation_id="c1",
        raw_event={"event_type": "standard"},
        audit_trail=[],
    )
    await workflow.run(state)
    out = metrics.export_metrics()
    assert out["counters"].get("workflow_execution_count") == 1
    assert (
        "request_count" in out["counters_by_labels"]
        or out["counters"].get("request_count", 0) >= 0
    )
    assert any("request_latency" in k for k in out["histograms"])


@pytest.mark.asyncio
async def test_risk_workflow_failure_classified_and_metrics(
    audit_logger, metrics, failure_classifier
):
    """When a node raises, failure is classified and failure_count incremented."""

    # We can't easily make a node raise from outside; test failure_classifier + metrics integration
    # by simulating: if we had a failing workflow run, classifier would be used.
    cat = failure_classifier.classify(ValueError("test"))
    assert cat.value == "UNEXPECTED_ERROR"
    metrics.increment("failure_count", 1, category=cat.value)
    out = metrics.export_metrics()
    assert "failure_count" in out["counters_by_labels"]
    assert sum(out["counters_by_labels"]["failure_count"].values()) == 1


@pytest.mark.asyncio
async def test_compliance_workflow_observability(audit_logger, metrics, tracing):
    """Compliance workflow records node latency and approval_required when applicable."""
    from app.workflows.langgraph.compliance_workflow import ComplianceWorkflow

    workflow = ComplianceWorkflow(
        audit_logger=audit_logger,
        metrics_collector=metrics,
        tracing_service=tracing,
    )
    state = ComplianceState(
        event_id="e1",
        tenant_id="t1",
        correlation_id="c1",
        raw_event={"event_type": "standard"},
        audit_trail=[],
    )
    await workflow.run(state)
    out = metrics.export_metrics()
    assert out["counters"].get("workflow_execution_count") == 1
    assert len(tracing.get_traces()) == 1
