"""Failure tests: node failure propagates, invalid state rejected, tenant isolation."""

from unittest.mock import AsyncMock

import pytest

from app.governance.audit_logger import AuditLogger
from app.workflows.langgraph.nodes.decision import make_decision
from app.workflows.langgraph.nodes.retrieval import retrieve_context
from app.workflows.langgraph.risk_workflow import RiskWorkflow
from app.workflows.langgraph.state_models import RiskState


@pytest.mark.asyncio
async def test_node_failure_propagates(audit_logger):
    """If audit logger raises, node failure must propagate."""
    failing_repo = AsyncMock()
    failing_repo.save = AsyncMock(side_effect=RuntimeError("save failed"))
    failing_audit = AuditLogger(repository=failing_repo)
    state = RiskState(event_id="e1", tenant_id="t1", correlation_id="c1", raw_event={})
    with pytest.raises(RuntimeError, match="save failed"):
        await retrieve_context(state, audit_logger=failing_audit)


@pytest.mark.asyncio
async def test_workflow_failure_propagates(audit_logger):
    """If a node raises, workflow run must propagate the error."""
    failing_repo = AsyncMock()
    failing_repo.save = AsyncMock(side_effect=ValueError("audit error"))
    failing_audit = AuditLogger(repository=failing_repo)
    workflow = RiskWorkflow(audit_logger=failing_audit, state_store=None)
    state = RiskState(
        event_id="e1",
        tenant_id="t1",
        correlation_id="c1",
        raw_event={"event_type": "standard"},
        audit_trail=[],
    )
    with pytest.raises(ValueError, match="audit error"):
        await workflow.run(state)


def test_invalid_state_rejected():
    """Invalid state (missing required fields) must be rejected by Pydantic."""
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        RiskState(event_id="e1")  # missing tenant_id, correlation_id
    # Minimal valid state
    state = RiskState(event_id="e1", tenant_id="t1", correlation_id="c1")
    assert state.tenant_id == "t1"


@pytest.mark.asyncio
async def test_tenant_isolation_state_carries_tenant(audit_logger, audit_repository):
    """Workflow must log and use tenant_id from state; no cross-tenant use."""
    state = RiskState(
        event_id="e1",
        tenant_id="tenant-alpha",
        correlation_id="c1",
        raw_event={},
        audit_trail=[],
    )
    out = await make_decision(
        state.transition(
            policy_result="PASS",
            risk_score=30.0,
            guardrail_result="OK",
        ),
        audit_logger=audit_logger,
    )
    assert out.tenant_id == "tenant-alpha"
    record = audit_repository.save.call_args[0][0]
    assert record.tenant_id == "tenant-alpha"
