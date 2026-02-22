"""Unit tests for event domain validators. Pure business rules, no infrastructure."""

from datetime import datetime, timezone

import pytest

from app.domain.exceptions import (
    DomainValidationError,
    InvalidMetadataError,
    InvalidStatusTransitionError,
    InvalidTenantError,
    RiskThresholdViolationError,
)
from app.domain.models.event import ComplianceEvent, EventStatus, RiskEvent
from app.domain.schemas.event import (
    ComplianceEventCreateRequest,
    RiskEventCreateRequest,
)
from app.domain.validators.event_validator import (
    RISK_SCORE_MAX,
    RISK_SCORE_MIN,
    validate_compliance_event,
    validate_compliance_event_create_request,
    validate_metadata_json_serializable,
    validate_risk_event,
    validate_risk_event_create_request,
    validate_risk_score,
    validate_status_transition,
    validate_tenant_id,
)

# --- validate_tenant_id ---


def test_validate_tenant_id_accepts_non_empty():
    """Non-empty tenant_id does not raise."""
    validate_tenant_id("tenant-1")
    validate_tenant_id(" " + "x" + " ")  # strip leaves non-empty


def test_validate_tenant_id_rejects_empty():
    """Empty or whitespace-only tenant_id raises InvalidTenantError."""
    with pytest.raises(InvalidTenantError) as exc_info:
        validate_tenant_id("")
    assert (
        "empty" in exc_info.value.message.lower()
        or "must not" in exc_info.value.message
    )

    with pytest.raises(InvalidTenantError):
        validate_tenant_id("   ")


# --- validate_risk_score ---


def test_validate_risk_score_accepts_none():
    """None risk_score is allowed."""
    validate_risk_score(None)


@pytest.mark.parametrize("score", [0.0, 50.0, 100.0, RISK_SCORE_MIN, RISK_SCORE_MAX])
def test_validate_risk_score_accepts_in_bounds(score: float):
    """Scores in [0, 100] are valid."""
    validate_risk_score(score)


@pytest.mark.parametrize("score", [-0.1, -1.0, 100.1, 101.0])
def test_validate_risk_score_rejects_out_of_bounds(score: float):
    """Scores outside [0, 100] raise RiskThresholdViolationError."""
    with pytest.raises(RiskThresholdViolationError) as exc_info:
        validate_risk_score(score)
    msg = str(exc_info.value)
    assert "0" in msg or str(RISK_SCORE_MIN) in msg
    assert "100" in msg or str(RISK_SCORE_MAX) in msg


# --- validate_metadata_json_serializable ---


def test_validate_metadata_none_allowed():
    """None metadata is allowed."""
    validate_metadata_json_serializable(None)


def test_validate_metadata_dict_serializable():
    """JSON-serializable dict is allowed."""
    validate_metadata_json_serializable({"a": 1, "b": "x", "c": [1, 2]})


def test_validate_metadata_rejects_non_serializable():
    """Non-JSON-serializable value raises InvalidMetadataError."""
    with pytest.raises(InvalidMetadataError) as exc_info:
        validate_metadata_json_serializable({"bad": object()})
    assert "JSON-serializable" in exc_info.value.message


# --- validate_status_transition ---


@pytest.mark.parametrize(
    "current,new",
    [
        (EventStatus.RECEIVED, EventStatus.VALIDATED),
        (EventStatus.RECEIVED, EventStatus.REJECTED),
        (EventStatus.PROCESSING, EventStatus.APPROVED),
    ],
)
def test_validate_status_transition_allowed(current: EventStatus, new: EventStatus):
    """Allowed transitions do not raise."""
    validate_status_transition(current, new)


def test_validate_status_transition_invalid_raises():
    """Invalid transition raises InvalidStatusTransitionError."""
    with pytest.raises(InvalidStatusTransitionError) as exc_info:
        validate_status_transition(EventStatus.RECEIVED, EventStatus.APPROVED)
    assert EventStatus.RECEIVED.value in str(exc_info.value)
    assert EventStatus.APPROVED.value in str(exc_info.value)


# --- validate_risk_event_create_request ---


def test_validate_risk_event_create_request_happy():
    """Valid request does not raise."""
    req = RiskEventCreateRequest(
        tenant_id="t1",
        risk_score=50.0,
        category="fraud",
        version="1.0",
    )
    validate_risk_event_create_request(req)


def test_validate_risk_event_create_request_empty_tenant_raises():
    """Empty tenant_id raises (via InvalidTenantError)."""
    req = RiskEventCreateRequest(tenant_id="  ", risk_score=None, version="1.0")
    with pytest.raises(InvalidTenantError):
        validate_risk_event_create_request(req)


def test_validate_risk_event_create_request_invalid_risk_score_raises():
    """Out-of-range risk_score raises RiskThresholdViolationError."""
    # model_construct bypasses Pydantic so we can test domain validator in isolation
    req = RiskEventCreateRequest.model_construct(
        tenant_id="t1", risk_score=150.0, version="1.0"
    )
    with pytest.raises(RiskThresholdViolationError):
        validate_risk_event_create_request(req)


def test_validate_risk_event_create_request_empty_version_raises():
    """Empty or missing version raises DomainValidationError."""
    # model_construct bypasses Pydantic so we can test domain validator in isolation
    req = RiskEventCreateRequest.model_construct(
        tenant_id="t1", risk_score=None, version=""
    )
    with pytest.raises(DomainValidationError) as exc_info:
        validate_risk_event_create_request(req)
    assert "version" in exc_info.value.message.lower()


# --- validate_compliance_event_create_request ---


def test_validate_compliance_event_create_request_happy():
    """Valid compliance request does not raise."""
    req = ComplianceEventCreateRequest(
        tenant_id="t1",
        regulation_ref="REG-1",
        version="1.0",
    )
    validate_compliance_event_create_request(req)


def test_validate_compliance_event_create_request_empty_version_raises():
    """Empty version raises DomainValidationError."""
    req = ComplianceEventCreateRequest(tenant_id="t1", version="  ")
    with pytest.raises(DomainValidationError) as exc_info:
        validate_compliance_event_create_request(req)
    assert "version" in exc_info.value.message.lower()


# --- validate_risk_event (entity) ---


def test_validate_risk_event_entity_happy():
    """Valid RiskEvent entity does not raise."""
    ev = RiskEvent(
        event_id="e1",
        tenant_id="t1",
        status=EventStatus.CREATED,
        created_at=datetime.now(timezone.utc),
        risk_score=50.0,
    )
    validate_risk_event(ev)


def test_validate_risk_event_entity_empty_tenant_raises():
    """RiskEvent with empty tenant_id raises InvalidTenantError."""
    ev = RiskEvent(
        event_id="e1",
        tenant_id="",
        status=EventStatus.CREATED,
        created_at=datetime.now(timezone.utc),
    )
    with pytest.raises(InvalidTenantError):
        validate_risk_event(ev)


def test_validate_risk_event_entity_invalid_score_raises():
    """RiskEvent with out-of-range risk_score raises RiskThresholdViolationError."""
    ev = RiskEvent(
        event_id="e1",
        tenant_id="t1",
        status=EventStatus.CREATED,
        created_at=datetime.now(timezone.utc),
        risk_score=200.0,
    )
    with pytest.raises(RiskThresholdViolationError):
        validate_risk_event(ev)


# --- validate_compliance_event (entity) ---


def test_validate_compliance_event_entity_happy():
    """Valid ComplianceEvent entity does not raise."""
    ev = ComplianceEvent(
        event_id="e1",
        tenant_id="t1",
        status=EventStatus.CREATED,
        created_at=datetime.now(timezone.utc),
    )
    validate_compliance_event(ev)


def test_validate_compliance_event_entity_empty_tenant_raises():
    """ComplianceEvent with empty tenant_id raises InvalidTenantError."""
    ev = ComplianceEvent(
        event_id="e1",
        tenant_id="   ",
        status=EventStatus.CREATED,
        created_at=datetime.now(timezone.utc),
    )
    with pytest.raises(InvalidTenantError):
        validate_compliance_event(ev)
