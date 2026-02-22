"""Security-layer exceptions. Typed, no HTTP."""


class SecurityError(Exception):
    """Base for all security-layer errors."""

    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


class AuthorizationError(SecurityError):
    """Raised when role does not have permission for the action."""


class TenantIsolationError(SecurityError):
    """Raised when resource tenant does not match request tenant (cross-tenant access)."""


class EncryptionError(SecurityError):
    """Raised when encryption/decryption fails (e.g. missing key, wrong key)."""
