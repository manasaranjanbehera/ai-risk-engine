"""FailureClassifier tests: exception mapping, UNEXPECTED_ERROR for unknown."""

from app.application.exceptions import IdempotencyConflictError
from app.domain.exceptions import (
    DomainValidationError,
    InvalidTenantError,
    RiskThresholdViolationError,
)
from app.governance.exceptions import ModelNotApprovedError, PromptNotApprovedError
from app.observability.failure_classifier import FailureCategory, FailureClassifier
from app.security.exceptions import AuthorizationError


def test_classify_validation_error():
    """DomainValidationError -> VALIDATION_ERROR."""
    assert (
        FailureClassifier.classify(DomainValidationError("bad"))
        == FailureCategory.VALIDATION_ERROR
    )
    assert (
        FailureClassifier.classify(InvalidTenantError("bad"))
        == FailureCategory.VALIDATION_ERROR
    )


def test_classify_policy_violation():
    """ModelNotApprovedError, PromptNotApprovedError -> POLICY_VIOLATION."""
    assert (
        FailureClassifier.classify(ModelNotApprovedError("x"))
        == FailureCategory.POLICY_VIOLATION
    )
    assert (
        FailureClassifier.classify(PromptNotApprovedError("prompt not found"))
        == FailureCategory.POLICY_VIOLATION
    )
    assert (
        FailureClassifier.classify(AuthorizationError("x"))
        == FailureCategory.POLICY_VIOLATION
    )


def test_classify_high_risk():
    """RiskThresholdViolationError -> HIGH_RISK."""
    assert (
        FailureClassifier.classify(RiskThresholdViolationError("x"))
        == FailureCategory.HIGH_RISK
    )


def test_classify_workflow_error():
    """IdempotencyConflictError -> WORKFLOW_ERROR."""
    assert (
        FailureClassifier.classify(IdempotencyConflictError("x"))
        == FailureCategory.WORKFLOW_ERROR
    )


def test_classify_unknown_exception_unexpected():
    """Unknown exception -> UNEXPECTED_ERROR."""
    assert (
        FailureClassifier.classify(ValueError("x")) == FailureCategory.UNEXPECTED_ERROR
    )
    assert (
        FailureClassifier.classify(RuntimeError("x"))
        == FailureCategory.UNEXPECTED_ERROR
    )
