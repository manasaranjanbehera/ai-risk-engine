"""Unit tests for domain exceptions. Hierarchy and message propagation."""

import pytest

from app.domain.exceptions import (
    DomainError,
    DomainValidationError,
    InvalidMetadataError,
    InvalidStatusTransitionError,
    InvalidTenantError,
    RiskThresholdViolationError,
)


def test_domain_error_base():
    """DomainError is the base and stores message."""
    err = DomainError("something went wrong")
    assert err.message == "something went wrong"
    assert str(err) == "something went wrong"
    assert isinstance(err, Exception)


def test_domain_validation_error_subclass():
    """DomainValidationError is a DomainError."""
    err = DomainValidationError("validation failed")
    assert err.message == "validation failed"
    assert isinstance(err, DomainError)


def test_invalid_status_transition_error_subclass():
    """InvalidStatusTransitionError is a DomainError."""
    err = InvalidStatusTransitionError(
        "Invalid status transition from received to approved"
    )
    assert "received" in err.message
    assert "approved" in err.message
    assert isinstance(err, DomainError)


def test_invalid_tenant_error_subclass():
    """InvalidTenantError is a DomainError."""
    err = InvalidTenantError("tenant_id must not be empty")
    assert err.message == "tenant_id must not be empty"
    assert isinstance(err, DomainError)


def test_risk_threshold_violation_error_subclass():
    """RiskThresholdViolationError is a DomainError."""
    err = RiskThresholdViolationError("risk_score must be between 0 and 100, got 150")
    assert "0" in err.message and "100" in err.message and "150" in err.message
    assert isinstance(err, DomainError)


def test_invalid_metadata_error_subclass():
    """InvalidMetadataError is a DomainError."""
    err = InvalidMetadataError("metadata must be JSON-serializable")
    assert err.message == "metadata must be JSON-serializable"
    assert isinstance(err, DomainError)


def test_domain_errors_can_be_raised_and_caught():
    """Domain exceptions are raised and caught as DomainError."""
    with pytest.raises(DomainError) as exc_info:
        raise InvalidTenantError("bad tenant")
    assert isinstance(exc_info.value, InvalidTenantError)
    assert exc_info.value.message == "bad tenant"
