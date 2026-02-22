"""Domain-specific exceptions. Pure domain layer — no infrastructure."""


class DomainError(Exception):
    """Base for all domain-layer errors."""

    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


class DomainValidationError(DomainError):
    """Raised when domain validation rules are violated."""


class InvalidStatusTransitionError(DomainError):
    """Raised when an event status transition is not allowed."""


class InvalidTenantError(DomainError):
    """Raised when tenant_id is invalid (e.g. empty)."""


class RiskThresholdViolationError(DomainError):
    """Raised when risk score is outside allowed bounds (e.g. not in 0–100)."""


class InvalidMetadataError(DomainError):
    """Raised when metadata is not JSON-serializable or otherwise invalid."""
