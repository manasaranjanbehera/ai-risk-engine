"""Security tests: tenant isolation enforced; cross-tenant access raises error."""

import pytest

from app.security.exceptions import TenantIsolationError
from app.security.tenant_context import TenantContext


def test_tenant_isolation_enforced_match_passes():
    TenantContext.validate_access("tenant-A", "tenant-A")


def test_cross_tenant_access_raises_error():
    with pytest.raises(TenantIsolationError) as exc_info:
        TenantContext.validate_access("tenant-A", "tenant-B")
    assert "tenant-A" in str(exc_info.value.message)
    assert "tenant-B" in str(exc_info.value.message)
    assert (
        "denied" in str(exc_info.value.message).lower()
        or "match" in str(exc_info.value.message).lower()
    )


def test_empty_resource_tenant_raises():
    with pytest.raises(TenantIsolationError):
        TenantContext.validate_access("", "tenant-B")


def test_empty_request_tenant_raises():
    with pytest.raises(TenantIsolationError):
        TenantContext.validate_access("tenant-A", "")
