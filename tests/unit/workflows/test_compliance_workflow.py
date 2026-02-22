"""Compliance workflow tests: regulatory flag escalation, low risk auto-approval, deterministic."""

from unittest.mock import AsyncMock

import pytest

from app.workflows.langgraph.compliance_workflow import ComplianceWorkflow
from app.workflows.langgraph.state_models import ComplianceState


@pytest.mark.asyncio
async def test_compliance_regulatory_flag_triggers_escalation(audit_logger):
    """Presence of regulatory_flags must lead to REQUIRE_APPROVAL and approval_required=True."""
    workflow = ComplianceWorkflow(audit_logger=audit_logger, state_store=None)
    state = ComplianceState(
        event_id="e1",
        tenant_id="t1",
        correlation_id="c1",
        raw_event={"event_type": "low_risk"},
        regulatory_flags=["GDPR"],
        audit_trail=[],
    )
    out = await workflow.run(state)
    assert out.final_decision == "REQUIRE_APPROVAL"
    assert out.approval_required is True


@pytest.mark.asyncio
async def test_compliance_low_risk_auto_approval(audit_logger):
    """Low risk, no flags, policy pass -> APPROVED, approval_required=False."""
    workflow = ComplianceWorkflow(audit_logger=audit_logger, state_store=None)
    state = ComplianceState(
        event_id="e2",
        tenant_id="t1",
        correlation_id="c2",
        raw_event={"event_type": "low_risk", "metadata": {"category": "normal"}},
        regulatory_flags=[],
        audit_trail=[],
    )
    out = await workflow.run(state)
    assert out.final_decision == "APPROVED"
    assert out.approval_required is False
    assert out.risk_score == 15.0


@pytest.mark.asyncio
async def test_compliance_deterministic_decision(audit_logger):
    """Same input must produce same decision (no randomness)."""
    workflow = ComplianceWorkflow(audit_logger=audit_logger, state_store=None)
    state = ComplianceState(
        event_id="e3",
        tenant_id="t1",
        correlation_id="c3",
        raw_event={"event_type": "standard"},
        regulatory_flags=[],
        audit_trail=[],
    )
    out1 = await workflow.run(state)
    state2 = ComplianceState(
        event_id="e3b",
        tenant_id="t1",
        correlation_id="c3b",
        raw_event={"event_type": "standard"},
        regulatory_flags=[],
        audit_trail=[],
    )
    out2 = await workflow.run(state2)
    assert out1.final_decision == out2.final_decision
    assert out1.risk_score == out2.risk_score


@pytest.mark.asyncio
async def test_compliance_idempotency_skip(audit_logger):
    """Cached compliance state must be returned without re-running."""
    cached = ComplianceState(
        event_id="e4",
        tenant_id="t1",
        correlation_id="c4",
        final_decision="APPROVED",
        approval_required=False,
        audit_trail=[{"node": "decision"}],
    )
    store = AsyncMock()
    store.get_compliance_state = AsyncMock(return_value=cached)
    store.set_compliance_state = AsyncMock(return_value=None)
    workflow = ComplianceWorkflow(audit_logger=audit_logger, state_store=store)
    state = ComplianceState(
        event_id="e4",
        tenant_id="t1",
        correlation_id="c4",
        raw_event={},
        audit_trail=[],
    )
    out = await workflow.run(state)
    assert out.final_decision == "APPROVED"
    store.get_compliance_state.assert_awaited_once_with("e4")
    store.set_compliance_state.assert_not_awaited()
