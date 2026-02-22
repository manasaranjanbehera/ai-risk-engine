"""Application-layer exceptions. Do not reuse domain exceptions."""


class ApplicationError(Exception):
    """Base for all application-layer errors."""

    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


class IdempotencyConflictError(ApplicationError):
    """Raised when idempotency state is inconsistent (e.g. conflict on cache)."""


class MessagingFailureError(ApplicationError):
    """Raised when publishing to the message broker fails. DB state remains authoritative."""
