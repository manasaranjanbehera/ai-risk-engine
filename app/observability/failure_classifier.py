"""Failure categorization for metrics and audit. Maps exceptions to taxonomy."""

from enum import Enum

from app.application.exceptions import ApplicationError, IdempotencyConflictError
from app.domain.exceptions import (
    DomainError,
    DomainValidationError,
    InvalidMetadataError,
    InvalidStatusTransitionError,
    InvalidTenantError,
    RiskThresholdViolationError,
)
from app.governance.exceptions import (
    GovernanceError,
    InvalidModelStateError,
    InvalidWorkflowStateError,
    ModelNotApprovedError,
)
from app.security.exceptions import (
    AuthorizationError,
    EncryptionError,
    SecurityError,
    TenantIsolationError,
)


class FailureCategory(str, Enum):
    """Taxonomy for failure classification."""

    VALIDATION_ERROR = "VALIDATION_ERROR"
    POLICY_VIOLATION = "POLICY_VIOLATION"
    HIGH_RISK = "HIGH_RISK"
    WORKFLOW_ERROR = "WORKFLOW_ERROR"
    INFRA_ERROR = "INFRA_ERROR"
    UNEXPECTED_ERROR = "UNEXPECTED_ERROR"


class FailureClassifier:
    """
    Classifies exceptions into FailureCategory. Integrates with MetricsCollector
    and AuditLogger via caller (caller increments metrics and logs audit).
    """

    @staticmethod
    def classify(exception: BaseException) -> FailureCategory:
        """Map exception to FailureCategory. Unknown -> UNEXPECTED_ERROR."""
        if isinstance(exception, DomainValidationError):
            return FailureCategory.VALIDATION_ERROR
        if isinstance(exception, (InvalidTenantError, InvalidMetadataError)):
            return FailureCategory.VALIDATION_ERROR
        if isinstance(exception, RiskThresholdViolationError):
            return FailureCategory.HIGH_RISK
        if isinstance(exception, (ModelNotApprovedError, InvalidModelStateError)):
            return FailureCategory.POLICY_VIOLATION
        if isinstance(
            exception, (InvalidWorkflowStateError, InvalidStatusTransitionError)
        ):
            return FailureCategory.WORKFLOW_ERROR
        if isinstance(exception, (AuthorizationError, TenantIsolationError)):
            return FailureCategory.POLICY_VIOLATION
        if isinstance(exception, (EncryptionError, SecurityError)):
            return FailureCategory.INFRA_ERROR
        if isinstance(exception, (IdempotencyConflictError, ApplicationError)):
            return FailureCategory.WORKFLOW_ERROR
        if isinstance(exception, GovernanceError):
            return FailureCategory.POLICY_VIOLATION
        if isinstance(exception, DomainError):
            return FailureCategory.VALIDATION_ERROR
        return FailureCategory.UNEXPECTED_ERROR
