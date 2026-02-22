"""EvaluationService tests: deterministic scoring, bounds, audit emitted."""

from unittest.mock import AsyncMock

import pytest

from app.observability.evaluation import EvaluationService


@pytest.mark.asyncio
async def test_evaluation_deterministic_quality_scoring():
    """Deterministic quality scoring for same inputs."""
    svc = EvaluationService()
    r1 = await svc.evaluate_decision(
        tenant_id="t1",
        event_id="e1",
        correlation_id="c1",
        final_decision="APPROVED",
        policy_result="PASS",
        guardrail_result="OK",
        risk_score=30.0,
    )
    r2 = await svc.evaluate_decision(
        tenant_id="t1",
        event_id="e1",
        correlation_id="c1",
        final_decision="APPROVED",
        policy_result="PASS",
        guardrail_result="OK",
        risk_score=30.0,
    )
    assert r1.confidence_score == r2.confidence_score
    assert r1.overall_quality_score == r2.overall_quality_score


@pytest.mark.asyncio
async def test_evaluation_scores_within_bounds():
    """Scores within [0, 1]."""
    svc = EvaluationService()
    r = await svc.evaluate_decision(
        tenant_id="t1",
        event_id="e1",
        correlation_id="c1",
        final_decision="REQUIRE_APPROVAL",
        policy_result="FAIL",
        guardrail_result="VIOLATION",
        risk_score=90.0,
    )
    assert 0 <= r.confidence_score <= 1
    assert 0 <= r.policy_alignment_score <= 1
    assert 0 <= r.guardrail_score <= 1
    assert 0 <= r.overall_quality_score <= 1


@pytest.mark.asyncio
async def test_evaluation_audit_emitted():
    """Audit event emitted when audit_logger provided."""
    audit = AsyncMock()
    svc = EvaluationService(audit_logger=audit)
    await svc.evaluate_decision(
        tenant_id="t1",
        event_id="e1",
        correlation_id="c1",
        final_decision="APPROVED",
        policy_result="PASS",
        guardrail_result="OK",
        risk_score=20.0,
    )
    audit.log_action.assert_awaited_once()
    call_kw = audit.log_action.call_args[1]
    assert call_kw["action"] == "evaluation_completed"
    assert "evaluation" in (call_kw.get("metadata") or {})
