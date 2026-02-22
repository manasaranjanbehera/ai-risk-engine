"""State tests: immutable transitions, serialization."""

import json


from app.workflows.langgraph.state_models import ComplianceState, RiskState


def test_risk_state_transition_returns_new_object():
    """Transition must return a new state; original unchanged."""
    state = RiskState(
        event_id="e1",
        tenant_id="t1",
        correlation_id="c1",
        raw_event={},
        risk_score=None,
    )
    new_state = state.transition(risk_score=50.0)
    assert new_state is not state
    assert new_state.risk_score == 50.0
    assert state.risk_score is None


def test_risk_state_immutable_transition_no_in_place_mutation():
    """Original state must not be mutated by transition."""
    state = RiskState(
        event_id="e1",
        tenant_id="t1",
        correlation_id="c1",
        audit_trail=[{"node": "retrieval"}],
    )
    new_state = state.transition(retrieved_context="ctx")
    assert len(state.audit_trail) == 1
    assert new_state.retrieved_context == "ctx"
    assert state.retrieved_context is None


def test_risk_state_serialization_roundtrip():
    """State must be fully serializable (model_dump_json / model_validate_json)."""
    state = RiskState(
        event_id="e1",
        tenant_id="t1",
        correlation_id="c1",
        raw_event={"k": "v"},
        retrieved_context="ctx",
        policy_result="PASS",
        risk_score=30.0,
        audit_trail=[{"node": "retrieval", "at": "2025-01-01T00:00:00Z"}],
    )
    data = state.model_dump_json()
    parsed = json.loads(data)
    assert parsed["event_id"] == "e1"
    assert parsed["risk_score"] == 30.0
    restored = RiskState.model_validate_json(data)
    assert restored.event_id == state.event_id
    assert restored.risk_score == state.risk_score
    assert restored.audit_trail == state.audit_trail


def test_compliance_state_has_regulatory_flags_and_approval_required():
    """ComplianceState must include regulatory_flags and approval_required."""
    state = ComplianceState(
        event_id="e1",
        tenant_id="t1",
        correlation_id="c1",
        regulatory_flags=["GDPR", "SOX"],
        approval_required=True,
    )
    assert state.regulatory_flags == ["GDPR", "SOX"]
    assert state.approval_required is True
    new_state = state.transition(approval_required=False)
    assert new_state.approval_required is False
    assert state.approval_required is True


def test_compliance_state_serialization_roundtrip():
    """ComplianceState must be fully serializable."""
    state = ComplianceState(
        event_id="e1",
        tenant_id="t1",
        correlation_id="c1",
        regulatory_flags=["F1"],
        approval_required=True,
    )
    restored = ComplianceState.model_validate_json(state.model_dump_json())
    assert restored.regulatory_flags == state.regulatory_flags
    assert restored.approval_required == state.approval_required
