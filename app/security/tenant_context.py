"""Strict tenant isolation. No cross-tenant access. No FastAPI."""

from app.security.exceptions import TenantIsolationError


class TenantContext:
    """Validate that request tenant matches resource tenant. No cross-tenant access."""

    @staticmethod
    def validate_access(resource_tenant: str, request_tenant: str) -> None:
        """
        If mismatch, raise TenantIsolationError.
        No cross-tenant access allowed.
        """
        if not resource_tenant or not request_tenant:
            raise TenantIsolationError(
                "Tenant isolation: resource_tenant and request_tenant must be non-empty"
            )
        if resource_tenant != request_tenant:
            raise TenantIsolationError(
                f"Tenant isolation: access denied. "
                f"Resource tenant '{resource_tenant}' does not match request tenant '{request_tenant}'"
            )
