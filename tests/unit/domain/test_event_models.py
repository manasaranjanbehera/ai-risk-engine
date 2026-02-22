"""Unit tests for domain event models. Lifecycle and transition rules are sacred."""

from datetime import datetime, timezone

import pytest

from app.domain.exceptions import InvalidStatusTransitionError
from app.domain.models.event import (
    BaseEvent,
    ComplianceEvent,
    EventStatus,
    RiskEvent,
)

# Canonical status transition matrix: from_status -> allowed to_statuses.
# This is the single source of truth for lifecycle rules; model and validator must match.
_EXPECTED_STATUS_TRANSITIONS = {
    EventStatus.RECEIVED: frozenset({EventStatus.VALIDATED, EventStatus.REJECTED}),
    EventStatus.CREATED: frozenset({EventStatus.VALIDATED, EventStatus.REJECTED}),
    EventStatus.VALIDATED: frozenset({EventStatus.PROCESSING}),
    EventStatus.PROCESSING: frozenset(
        {EventStatus.APPROVED, EventStatus.REJECTED, EventStatus.FAILED}
    ),
    EventStatus.APPROVED: frozenset(),
    EventStatus.REJECTED: frozenset(),
    EventStatus.FAILED: frozenset(),
}


# --- EventStatus ---


def test_event_status_values():
    """EventStatus enum exposes expected lifecycle values."""
    assert EventStatus.RECEIVED.value == "received"
    assert EventStatus.CREATED.value == "created"
    assert EventStatus.VALIDATED.value == "validated"
    assert EventStatus.PROCESSING.value == "processing"
    assert EventStatus.APPROVED.value == "approved"
    assert EventStatus.REJECTED.value == "rejected"
    assert EventStatus.FAILED.value == "failed"


# --- BaseEvent construction and transition_to ---


def _base_event(
    event_id: str = "evt-1",
    tenant_id: str = "t1",
    status: EventStatus = EventStatus.RECEIVED,
) -> BaseEvent:
    return BaseEvent(
        event_id=event_id,
        tenant_id=tenant_id,
        status=status,
        created_at=datetime.now(timezone.utc),
        metadata=None,
    )


def test_base_event_construction():
    """BaseEvent stores identity, tenant, status, and timestamps."""
    ev = _base_event(event_id="evt-x", tenant_id="tenant-y", status=EventStatus.CREATED)
    assert ev.event_id == "evt-x"
    assert ev.tenant_id == "tenant-y"
    assert ev.status == EventStatus.CREATED
    assert ev.metadata is None


@pytest.mark.parametrize(
    "from_status,to_status",
    [
        (EventStatus.RECEIVED, EventStatus.VALIDATED),
        (EventStatus.RECEIVED, EventStatus.REJECTED),
        (EventStatus.CREATED, EventStatus.VALIDATED),
        (EventStatus.CREATED, EventStatus.REJECTED),
        (EventStatus.VALIDATED, EventStatus.PROCESSING),
        (EventStatus.PROCESSING, EventStatus.APPROVED),
        (EventStatus.PROCESSING, EventStatus.REJECTED),
        (EventStatus.PROCESSING, EventStatus.FAILED),
    ],
)
def test_transition_to_allowed(from_status: EventStatus, to_status: EventStatus):
    """Allowed status transitions mutate status in place."""
    ev = _base_event(status=from_status)
    ev.transition_to(to_status)
    assert ev.status == to_status


@pytest.mark.parametrize(
    "from_status,to_status",
    [
        (EventStatus.RECEIVED, EventStatus.APPROVED),
        (EventStatus.RECEIVED, EventStatus.PROCESSING),
        (EventStatus.VALIDATED, EventStatus.REJECTED),
        (EventStatus.PROCESSING, EventStatus.VALIDATED),
        (EventStatus.APPROVED, EventStatus.PROCESSING),
        (EventStatus.REJECTED, EventStatus.VALIDATED),
        (EventStatus.FAILED, EventStatus.PROCESSING),
    ],
)
def test_transition_to_invalid_raises(from_status: EventStatus, to_status: EventStatus):
    """Invalid transitions raise InvalidStatusTransitionError."""
    ev = _base_event(status=from_status)
    with pytest.raises(InvalidStatusTransitionError) as exc_info:
        ev.transition_to(to_status)
    assert from_status.value in str(exc_info.value)
    assert to_status.value in str(exc_info.value)
    assert ev.status == from_status


def test_terminal_statuses_have_no_transitions():
    """APPROVED, REJECTED, FAILED do not allow any transition."""
    for terminal in (EventStatus.APPROVED, EventStatus.REJECTED, EventStatus.FAILED):
        ev = _base_event(status=terminal)
        with pytest.raises(InvalidStatusTransitionError):
            ev.transition_to(EventStatus.VALIDATED)
        assert ev.status == terminal


def test_status_transition_matrix_explicit():
    """
    Explicit test for the status transition matrix (_STATUS_TRANSITIONS).
    Every EventStatus has an entry; allowed transitions succeed, others raise.
    Ensures domain model and validator stay in sync with this canonical matrix.
    """
    all_statuses = set(EventStatus)
    assert (
        set(_EXPECTED_STATUS_TRANSITIONS.keys()) == all_statuses
    ), "every status must have transition entry"

    for from_status, allowed_to in _EXPECTED_STATUS_TRANSITIONS.items():
        for to_status in allowed_to:
            ev = _base_event(status=from_status)
            ev.transition_to(to_status)
            assert ev.status == to_status

        for to_status in all_statuses - allowed_to:
            ev = _base_event(status=from_status)
            with pytest.raises(InvalidStatusTransitionError):
                ev.transition_to(to_status)
            assert ev.status == from_status


# --- RiskEvent ---


def test_risk_event_construction():
    """RiskEvent extends BaseEvent with risk_score and category."""
    ev = RiskEvent(
        event_id="r-1",
        tenant_id="t1",
        status=EventStatus.CREATED,
        created_at=datetime.now(timezone.utc),
        metadata={"k": "v"},
        risk_score=75.0,
        category="fraud",
    )
    assert ev.event_id == "r-1"
    assert ev.tenant_id == "t1"
    assert ev.status == EventStatus.CREATED
    assert ev.risk_score == 75.0
    assert ev.category == "fraud"
    assert ev.metadata == {"k": "v"}


def test_risk_event_transition_to_inherited():
    """RiskEvent uses same transition rules as BaseEvent."""
    ev = RiskEvent(
        event_id="r-1",
        tenant_id="t1",
        status=EventStatus.RECEIVED,
        created_at=datetime.now(timezone.utc),
        risk_score=50.0,
    )
    ev.transition_to(EventStatus.VALIDATED)
    assert ev.status == EventStatus.VALIDATED


# --- ComplianceEvent ---


def test_compliance_event_construction():
    """ComplianceEvent extends BaseEvent with regulation_ref and compliance_type."""
    ev = ComplianceEvent(
        event_id="c-1",
        tenant_id="t1",
        status=EventStatus.CREATED,
        created_at=datetime.now(timezone.utc),
        regulation_ref="REG-123",
        compliance_type="kyc",
    )
    assert ev.event_id == "c-1"
    assert ev.tenant_id == "t1"
    assert ev.regulation_ref == "REG-123"
    assert ev.compliance_type == "kyc"


def test_compliance_event_transition_to_inherited():
    """ComplianceEvent uses same transition rules as BaseEvent."""
    ev = ComplianceEvent(
        event_id="c-1",
        tenant_id="t1",
        status=EventStatus.PROCESSING,
        created_at=datetime.now(timezone.utc),
    )
    ev.transition_to(EventStatus.APPROVED)
    assert ev.status == EventStatus.APPROVED
