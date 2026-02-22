"""Validators for event domain rules. Pure functions, no infrastructure or DB access."""

import json
from typing import Any, Dict, Optional

from app.domain.exceptions import (
    DomainValidationError,
    InvalidMetadataError,
    InvalidStatusTransitionError,
    InvalidTenantError,
    RiskThresholdViolationError,
)
from app.domain.models.event import EventStatus, RiskEvent, ComplianceEvent
from app.domain.schemas.event import (
    ComplianceEventCreateRequest,
    RiskEventCreateRequest,
)

# Risk score bounds (domain constant; avoid magic numbers)
RISK_SCORE_MIN = 0
RISK_SCORE_MAX = 100


def validate_tenant_id(tenant_id: str) -> None:
    """Enforce tenant constraint: must not be empty. Raises InvalidTenantError if invalid."""
    if not tenant_id or not tenant_id.strip():
        raise InvalidTenantError("tenant_id must not be empty")


def validate_risk_score(risk_score: Optional[float]) -> None:
    """Enforce risk threshold: if present, must be in [0, 100]. Raises RiskThresholdViolationError if invalid."""
    if risk_score is None:
        return
    if not (RISK_SCORE_MIN <= risk_score <= RISK_SCORE_MAX):
        raise RiskThresholdViolationError(
            f"risk_score must be between {RISK_SCORE_MIN} and {RISK_SCORE_MAX}, got {risk_score}"
        )


def validate_metadata_json_serializable(metadata: Optional[Dict[str, Any]]) -> None:
    """Ensure metadata is JSON-serializable. Raises InvalidMetadataError if not."""
    if metadata is None:
        return
    try:
        json.dumps(metadata)
    except (TypeError, ValueError) as e:
        raise InvalidMetadataError("metadata must be JSON-serializable") from e


def validate_status_transition(current: EventStatus, new: EventStatus) -> None:
    """Validate that transition from current to new status is allowed. Raises InvalidStatusTransitionError if not."""
    allowed = _allowed_transitions().get(current, frozenset())
    if new not in allowed:
        raise InvalidStatusTransitionError(
            f"Invalid status transition from {current.value} to {new.value}"
        )


def _allowed_transitions() -> dict:
    """Allowed status transitions. Pure data, no side effects."""
    return {
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


def validate_risk_event_create_request(request: RiskEventCreateRequest) -> None:
    """
    Validate RiskEvent creation request: tenant, risk score, metadata, version.
    Raises domain exceptions on violation.
    """
    validate_tenant_id(request.tenant_id)
    validate_risk_score(request.risk_score)
    validate_metadata_json_serializable(request.metadata)
    if not request.version or not request.version.strip():
        raise DomainValidationError("version must be set and non-empty")


def validate_compliance_event_create_request(
    request: ComplianceEventCreateRequest,
) -> None:
    """
    Validate ComplianceEvent creation request: tenant, metadata, version.
    Raises domain exceptions on violation.
    """
    validate_tenant_id(request.tenant_id)
    validate_metadata_json_serializable(request.metadata)
    if not request.version or not request.version.strip():
        raise DomainValidationError("version must be set and non-empty")


def validate_risk_event(entity: RiskEvent) -> None:
    """Validate RiskEvent entity business rules: tenant, risk score, status lifecycle consistency."""
    validate_tenant_id(entity.tenant_id)
    validate_risk_score(entity.risk_score)


def validate_compliance_event(entity: ComplianceEvent) -> None:
    """Validate ComplianceEvent entity business rules: tenant constraint."""
    validate_tenant_id(entity.tenant_id)
