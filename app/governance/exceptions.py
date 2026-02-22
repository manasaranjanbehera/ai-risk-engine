"""Governance-layer exceptions. Typed, no HTTP."""


class GovernanceError(Exception):
    """Base for all governance-layer errors."""

    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


class ModelNotApprovedError(GovernanceError):
    """Raised when attempting to deploy or use an unapproved model."""


class InvalidModelStateError(GovernanceError):
    """Raised when model state transition is not allowed (e.g. approve twice)."""


class InvalidWorkflowStateError(GovernanceError):
    """Raised when approval workflow status transition is not allowed."""


class PromptNotApprovedError(GovernanceError):
    """Raised when attempting to use a prompt that is not approved or not found."""
