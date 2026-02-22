"""
Chaos: workflow failures (node crash mid-workflow, exception in node).
System must: fail gracefully, classify failure, maintain audit integrity, not corrupt state.
Tests either inject real failure via mocks or are explicitly named for what they do (success-path).
"""

import pytest
from unittest.mock import AsyncMock, patch

from app.domain.exceptions import DomainValidationError
from app.observability.failure_classifier import FailureClassifier
from app.observability.metrics import MetricsCollector
from app.workflows.langgraph.state_models import RiskState
from app.workflows.langgraph.risk_workflow import RiskWorkflow


@pytest.fixture
def audit_logger():
    audit = AsyncMock()
    audit.log_action = AsyncMock(return_value=None)
    return audit


@pytest.mark.asyncio
async def test_workflow_success_path_metrics_recorded(audit_logger):
    """Success path: workflow runs to completion and execution metrics are recorded.
    Does not inject failure; for failure injection see test_workflow_injected_failure_classified_and_metrics.
    """
    metrics = MetricsCollector()
    classifier = FailureClassifier()
    workflow = RiskWorkflow(
        audit_logger=audit_logger,
        state_store=None,
        metrics_collector=metrics,
        failure_classifier=classifier,
    )
    state = RiskState(
        event_id="chaos-1",
        tenant_id="t1",
        correlation_id="c1",
        raw_event={"event_type": "chaos"},
        model_version="simulated@1",
        prompt_version=1,
        audit_trail=[],
    )
    result = await workflow.run(state)
    assert result.event_id == "chaos-1"
    out = metrics.export_metrics()
    assert out["counters"].get("workflow_execution_count", 0) >= 1


@pytest.mark.asyncio
async def test_workflow_injected_failure_classified_and_metrics(audit_logger):
    """Chaos: inject node failure via mock; workflow classifies exception and records failure_count.
    Patches retrieval node to raise DomainValidationError so the workflow's except path runs.
    """
    from app.workflows.langgraph import risk_workflow

    async def failing_retrieval(state, *, audit_logger):
        raise DomainValidationError("chaos injection: simulated node failure")

    metrics = MetricsCollector()
    classifier = FailureClassifier()
    workflow = RiskWorkflow(
        audit_logger=audit_logger,
        state_store=None,
        metrics_collector=metrics,
        failure_classifier=classifier,
    )
    state = RiskState(
        event_id="chaos-fail-1",
        tenant_id="t1",
        correlation_id="c1",
        raw_event={"event_type": "chaos"},
        model_version="simulated@1",
        prompt_version=1,
        audit_trail=[],
    )
    with patch.object(risk_workflow, "retrieve_context", side_effect=failing_retrieval):
        with pytest.raises(DomainValidationError, match="chaos injection"):
            await workflow.run(state)
    out = metrics.export_metrics()
    assert out["counters_by_labels"].get("failure_count") is not None
    failure_by_cat = out["counters_by_labels"]["failure_count"]
    assert any("VALIDATION_ERROR" in k for k in failure_by_cat)
    assert sum(failure_by_cat.values()) == 1


@pytest.mark.asyncio
async def test_failure_classifier_maps_exceptions():
    """Failure classifier maps known exceptions to categories."""
    from app.application.exceptions import IdempotencyConflictError
    from app.domain.exceptions import DomainValidationError

    classifier = FailureClassifier()
    assert classifier.classify(DomainValidationError("x")).value == "VALIDATION_ERROR"
    assert classifier.classify(IdempotencyConflictError("x")).value == "WORKFLOW_ERROR"
