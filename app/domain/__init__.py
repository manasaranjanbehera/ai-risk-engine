"""Domain layer: models, schemas, validators, exceptions. Pure business logic only."""

from app.domain.exceptions import (
    DomainError,
    DomainValidationError,
    InvalidMetadataError,
    InvalidStatusTransitionError,
    InvalidTenantError,
    RiskThresholdViolationError,
)
from app.domain.models import ComplianceEvent, EventStatus, RiskEvent
from app.domain.schemas import (
    ComplianceEventCreateRequest,
    EventResponse,
    RiskEventCreateRequest,
)
from app.domain.validators import (
    validate_compliance_event,
    validate_compliance_event_create_request,
    validate_risk_event,
    validate_risk_event_create_request,
    validate_status_transition,
    validate_tenant_id,
)

__all__ = [
    "ComplianceEvent",
    "ComplianceEventCreateRequest",
    "DomainError",
    "DomainValidationError",
    "EventResponse",
    "EventStatus",
    "InvalidMetadataError",
    "InvalidStatusTransitionError",
    "InvalidTenantError",
    "RiskEvent",
    "RiskEventCreateRequest",
    "RiskThresholdViolationError",
    "validate_compliance_event",
    "validate_compliance_event_create_request",
    "validate_risk_event",
    "validate_risk_event_create_request",
    "validate_status_transition",
    "validate_tenant_id",
]
