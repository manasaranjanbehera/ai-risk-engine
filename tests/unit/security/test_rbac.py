"""Security tests: RBAC permission matrix fully tested."""

import pytest

from app.security.exceptions import AuthorizationError
from app.security.rbac import RBACService, Role


@pytest.fixture
def rbac():
    return RBACService()


# Permission matrix:
# Role      Create  Approve  View  Register Model
# ADMIN     ✓       ✓       ✓     ✓
# ANALYST   ✓       ✗       ✓     ✗
# APPROVER  ✗       ✓       ✓     ✗
# VIEWER    ✗       ✗       ✓     ✗


def test_admin_has_all_permissions(rbac):
    rbac.check_permission(Role.ADMIN, "create")
    rbac.check_permission(Role.ADMIN, "approve")
    rbac.check_permission(Role.ADMIN, "view")
    rbac.check_permission(Role.ADMIN, "register_model")


def test_analyst_create_view_ok_approve_register_denied(rbac):
    rbac.check_permission(Role.ANALYST, "create")
    rbac.check_permission(Role.ANALYST, "view")
    with pytest.raises(AuthorizationError):
        rbac.check_permission(Role.ANALYST, "approve")
    with pytest.raises(AuthorizationError):
        rbac.check_permission(Role.ANALYST, "register_model")


def test_approver_approve_view_ok_create_register_denied(rbac):
    rbac.check_permission(Role.APPROVER, "approve")
    rbac.check_permission(Role.APPROVER, "view")
    with pytest.raises(AuthorizationError):
        rbac.check_permission(Role.APPROVER, "create")
    with pytest.raises(AuthorizationError):
        rbac.check_permission(Role.APPROVER, "register_model")


def test_viewer_only_view(rbac):
    rbac.check_permission(Role.VIEWER, "view")
    with pytest.raises(AuthorizationError):
        rbac.check_permission(Role.VIEWER, "create")
    with pytest.raises(AuthorizationError):
        rbac.check_permission(Role.VIEWER, "approve")
    with pytest.raises(AuthorizationError):
        rbac.check_permission(Role.VIEWER, "register_model")


def test_unknown_action_raises(rbac):
    with pytest.raises(AuthorizationError):
        rbac.check_permission(Role.ADMIN, "unknown_action")
