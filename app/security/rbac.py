"""Role-based access control. No FastAPI."""

from enum import Enum

from app.security.exceptions import AuthorizationError


class Role(Enum):
    ADMIN = "ADMIN"
    ANALYST = "ANALYST"
    APPROVER = "APPROVER"
    VIEWER = "VIEWER"


# Permission matrix:
# Role      Create  Approve  View  Register Model
# ADMIN     ✓       ✓       ✓     ✓
# ANALYST   ✓       ✗       ✓     ✗
# APPROVER  ✗       ✓       ✓     ✗
# VIEWER    ✗       ✗       ✓     ✗

_ACTION_PERMISSIONS: dict[tuple[Role, str], bool] = {
    (Role.ADMIN, "create"): True,
    (Role.ADMIN, "approve"): True,
    (Role.ADMIN, "view"): True,
    (Role.ADMIN, "register_model"): True,
    (Role.ANALYST, "create"): True,
    (Role.ANALYST, "approve"): False,
    (Role.ANALYST, "view"): True,
    (Role.ANALYST, "register_model"): False,
    (Role.APPROVER, "create"): False,
    (Role.APPROVER, "approve"): True,
    (Role.APPROVER, "view"): True,
    (Role.APPROVER, "register_model"): False,
    (Role.VIEWER, "create"): False,
    (Role.VIEWER, "approve"): False,
    (Role.VIEWER, "view"): True,
    (Role.VIEWER, "register_model"): False,
}


class RBACService:
    """Check permission for role and action. Raise AuthorizationError if invalid."""

    def check_permission(self, role: Role, action: str) -> None:
        """Raises AuthorizationError if role does not have permission for action."""
        key = (role, action)
        if key not in _ACTION_PERMISSIONS or not _ACTION_PERMISSIONS[key]:
            raise AuthorizationError(
                f"Role {role.value} does not have permission for action '{action}'"
            )
