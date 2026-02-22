"""Node tests: valid state -> correct transformation, audit emitted, version logged."""

import pytest

from app.workflows.langgraph.nodes.decision import make_decision
from app.workflows.langgraph.nodes.guardrails import apply_guardrails
from app.workflows.langgraph.nodes.policy_validation import validate_policy
from app.workflows.langgraph.nodes.retrieval import retrieve_context
from app.workflows.langgraph.nodes.risk_scoring import score_risk
from app.workflows.langgraph.state_models import RiskState


@pytest.mark.asyncio
async def test_retrieval_valid_state_correct_transformation(audit_logger):
    state = RiskState(
        event_id="e1",
        tenant_id="t1",
        correlation_id="c1",
        raw_event={"event_type": "standard"},
        model_version="v1",
        prompt_version=2,
        audit_trail=[],
    )
    out = await retrieve_context(state, audit_logger=audit_logger)
    assert out.retrieved_context == "simulated_context:t1:standard"
    assert len(out.audit_trail) == 1
    assert out.audit_trail[0]["node"] == "retrieval"
    assert out.audit_trail[0]["action"] == "context_retrieved"
    assert out.audit_trail[0]["model_version"] == "v1"
    assert out.audit_trail[0]["prompt_version"] == 2


@pytest.mark.asyncio
async def test_retrieval_audit_emitted(audit_logger, audit_repository):
    state = RiskState(event_id="e1", tenant_id="t1", correlation_id="c1", raw_event={})
    await retrieve_context(state, audit_logger=audit_logger)
    assert audit_repository.save.await_count == 1
    record = audit_repository.save.call_args[0][0]
    assert record.action == "context_retrieved"
    assert record.metadata is not None
    assert "model_version" in record.metadata
    assert "prompt_version" in record.metadata


@pytest.mark.asyncio
async def test_policy_validation_pass(audit_logger):
    state = RiskState(
        event_id="e1",
        tenant_id="t1",
        correlation_id="c1",
        raw_event={"metadata": {"category": "normal"}},
        audit_trail=[],
    )
    out = await validate_policy(state, audit_logger=audit_logger)
    assert out.policy_result == "PASS"


@pytest.mark.asyncio
async def test_policy_validation_fail_sensitive(audit_logger):
    state = RiskState(
        event_id="e1",
        tenant_id="t1",
        correlation_id="c1",
        raw_event={"metadata": {"category": "sensitive"}},
        audit_trail=[],
    )
    out = await validate_policy(state, audit_logger=audit_logger)
    assert out.policy_result == "FAIL"


@pytest.mark.asyncio
async def test_policy_validation_audit_emitted(audit_logger, audit_repository):
    state = RiskState(event_id="e1", tenant_id="t1", correlation_id="c1", raw_event={})
    await validate_policy(state, audit_logger=audit_logger)
    assert audit_repository.save.await_count == 1
    assert audit_repository.save.call_args[0][0].metadata["model_version"] is not None


@pytest.mark.asyncio
async def test_risk_scoring_deterministic(audit_logger):
    state = RiskState(
        event_id="e1",
        tenant_id="t1",
        correlation_id="c1",
        raw_event={"event_type": "high_risk"},
        audit_trail=[],
    )
    out = await score_risk(state, audit_logger=audit_logger)
    assert out.risk_score == 85.0
    out2 = await score_risk(state, audit_logger=audit_logger)
    assert out2.risk_score == 85.0


@pytest.mark.asyncio
async def test_risk_scoring_standard_event(audit_logger):
    state = RiskState(
        event_id="e1",
        tenant_id="t1",
        correlation_id="c1",
        raw_event={"event_type": "standard"},
        audit_trail=[],
    )
    out = await score_risk(state, audit_logger=audit_logger)
    assert out.risk_score == 30.0


@pytest.mark.asyncio
async def test_guardrails_ok(audit_logger):
    state = RiskState(
        event_id="e1",
        tenant_id="t1",
        correlation_id="c1",
        risk_score=30.0,
        raw_event={},
        audit_trail=[],
    )
    out = await apply_guardrails(state, audit_logger=audit_logger)
    assert out.guardrail_result == "OK"


@pytest.mark.asyncio
async def test_guardrails_violation_high_risk(audit_logger):
    state = RiskState(
        event_id="e1",
        tenant_id="t1",
        correlation_id="c1",
        risk_score=85.0,
        raw_event={},
        audit_trail=[],
    )
    out = await apply_guardrails(state, audit_logger=audit_logger)
    assert out.guardrail_result == "VIOLATION"


@pytest.mark.asyncio
async def test_decision_approved(audit_logger):
    state = RiskState(
        event_id="e1",
        tenant_id="t1",
        correlation_id="c1",
        policy_result="PASS",
        risk_score=30.0,
        guardrail_result="OK",
        audit_trail=[],
    )
    out = await make_decision(state, audit_logger=audit_logger)
    assert out.final_decision == "APPROVED"


@pytest.mark.asyncio
async def test_decision_require_approval_policy_fail(audit_logger):
    state = RiskState(
        event_id="e1",
        tenant_id="t1",
        correlation_id="c1",
        policy_result="FAIL",
        risk_score=30.0,
        guardrail_result="OK",
        audit_trail=[],
    )
    out = await make_decision(state, audit_logger=audit_logger)
    assert out.final_decision == "REQUIRE_APPROVAL"


@pytest.mark.asyncio
async def test_decision_require_approval_high_risk(audit_logger):
    state = RiskState(
        event_id="e1",
        tenant_id="t1",
        correlation_id="c1",
        policy_result="PASS",
        risk_score=85.0,
        guardrail_result="OK",
        audit_trail=[],
    )
    out = await make_decision(state, audit_logger=audit_logger)
    assert out.final_decision == "REQUIRE_APPROVAL"


@pytest.mark.asyncio
async def test_decision_audit_emitted(audit_logger, audit_repository):
    state = RiskState(
        event_id="e1",
        tenant_id="t1",
        correlation_id="c1",
        policy_result="PASS",
        risk_score=30.0,
        guardrail_result="OK",
        audit_trail=[],
    )
    await make_decision(state, audit_logger=audit_logger)
    assert audit_repository.save.await_count == 1
    assert audit_repository.save.call_args[0][0].action == "decision_made"
