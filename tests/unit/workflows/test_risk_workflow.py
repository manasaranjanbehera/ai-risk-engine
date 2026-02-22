"""Risk workflow tests: happy path, policy fail, high risk, idempotency, audit trail."""

from unittest.mock import AsyncMock

import pytest

from app.workflows.langgraph.risk_workflow import RiskWorkflow
from app.workflows.langgraph.state_models import RiskState


@pytest.mark.asyncio
async def test_risk_workflow_full_happy_path(audit_logger):
    """Full run: retrieval -> policy -> scoring -> guardrails -> decision -> APPROVED."""
    workflow = RiskWorkflow(audit_logger=audit_logger, state_store=None)
    state = RiskState(
        event_id="e1",
        tenant_id="t1",
        correlation_id="c1",
        raw_event={"event_type": "standard", "metadata": {"category": "normal"}},
        audit_trail=[],
    )
    out = await workflow.run(state)
    assert out.final_decision == "APPROVED"
    assert out.retrieved_context is not None
    assert out.policy_result == "PASS"
    assert out.risk_score == 30.0
    assert out.guardrail_result == "OK"


@pytest.mark.asyncio
async def test_risk_workflow_policy_fail_triggers_approval(audit_logger):
    """Policy FAIL must lead to REQUIRE_APPROVAL."""
    workflow = RiskWorkflow(audit_logger=audit_logger, state_store=None)
    state = RiskState(
        event_id="e2",
        tenant_id="t1",
        correlation_id="c2",
        raw_event={"event_type": "standard", "metadata": {"category": "sensitive"}},
        audit_trail=[],
    )
    out = await workflow.run(state)
    assert out.policy_result == "FAIL"
    assert out.final_decision == "REQUIRE_APPROVAL"


@pytest.mark.asyncio
async def test_risk_workflow_high_risk_triggers_approval(audit_logger):
    """High risk score must lead to REQUIRE_APPROVAL."""
    workflow = RiskWorkflow(audit_logger=audit_logger, state_store=None)
    state = RiskState(
        event_id="e3",
        tenant_id="t1",
        correlation_id="c3",
        raw_event={"event_type": "high_risk"},
        audit_trail=[],
    )
    out = await workflow.run(state)
    assert out.risk_score == 85.0
    assert out.final_decision == "REQUIRE_APPROVAL"


@pytest.mark.asyncio
async def test_risk_workflow_idempotency_skip(audit_logger):
    """If state_store returns cached state, workflow must return it without re-running nodes."""
    cached_state = RiskState(
        event_id="e4",
        tenant_id="t1",
        correlation_id="c4",
        final_decision="APPROVED",
        risk_score=20.0,
        audit_trail=[{"node": "decision", "action": "decision_made"}],
    )
    store = AsyncMock()
    store.get_risk_state = AsyncMock(return_value=cached_state)
    store.set_risk_state = AsyncMock(return_value=None)
    workflow = RiskWorkflow(audit_logger=audit_logger, state_store=store)
    state = RiskState(
        event_id="e4",
        tenant_id="t1",
        correlation_id="c4",
        raw_event={},
        audit_trail=[],
    )
    out = await workflow.run(state)
    assert out.final_decision == "APPROVED"
    assert out.risk_score == 20.0
    store.get_risk_state.assert_awaited_once_with("e4")
    store.set_risk_state.assert_not_awaited()


@pytest.mark.asyncio
async def test_risk_workflow_audit_trail_length(audit_logger):
    """After full run, audit_trail must have one entry per node (5 nodes)."""
    workflow = RiskWorkflow(audit_logger=audit_logger, state_store=None)
    state = RiskState(
        event_id="e5",
        tenant_id="t1",
        correlation_id="c5",
        raw_event={"event_type": "standard"},
        audit_trail=[],
    )
    out = await workflow.run(state)
    nodes_in_trail = [e["node"] for e in out.audit_trail]
    assert "retrieval" in nodes_in_trail
    assert "policy_validation" in nodes_in_trail
    assert "risk_scoring" in nodes_in_trail
    assert "guardrails" in nodes_in_trail
    assert "decision" in nodes_in_trail
    assert len(out.audit_trail) == 5


@pytest.mark.asyncio
async def test_risk_workflow_stores_result_when_store_provided(audit_logger):
    """When state_store is provided, final state must be stored after run."""
    store = AsyncMock()
    store.get_risk_state = AsyncMock(return_value=None)
    store.set_risk_state = AsyncMock(return_value=None)
    workflow = RiskWorkflow(audit_logger=audit_logger, state_store=store)
    state = RiskState(
        event_id="e6",
        tenant_id="t1",
        correlation_id="c6",
        raw_event={"event_type": "standard"},
        audit_trail=[],
    )
    out = await workflow.run(state)
    store.set_risk_state.assert_awaited_once()
    call_args = store.set_risk_state.call_args
    assert call_args[0][0] == "e6"
    assert call_args[0][1].event_id == "e6"
    assert call_args[0][1].final_decision == out.final_decision
