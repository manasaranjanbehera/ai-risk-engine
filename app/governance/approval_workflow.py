"""Human-in-the-loop gating. No auto-approve; RBAC enforced; audit trail. No FastAPI."""

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Optional, Protocol

from app.governance.audit_logger import AuditLogger
from app.governance.exceptions import InvalidWorkflowStateError
from app.security.rbac import RBACService, Role


class ApprovalStatus(str, Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


@dataclass(frozen=True)
class ApprovalRequest:
    """Single approval request. Status transitions enforced."""

    request_id: str
    resource_type: str
    resource_id: str
    requested_by: str
    status: ApprovalStatus
    created_at: datetime
    decided_by: Optional[str] = None
    decided_at: Optional[datetime] = None
    reason: Optional[str] = None


class ApprovalRepository(Protocol):
    """Storage for approval requests."""

    async def save(self, request: ApprovalRequest) -> None: ...

    async def get(self, request_id: str) -> Optional[ApprovalRequest]: ...


class ApprovalWorkflow:
    """
    Human-in-the-loop gating.
    Cannot auto-approve. Must enforce RBAC (only APPROVER role). Must log audit trail.
    Status transitions enforced.
    """

    def __init__(
        self,
        repository: ApprovalRepository,
        audit_logger: AuditLogger,
        rbac: RBACService,
    ) -> None:
        self._repo = repository
        self._audit = audit_logger
        self._rbac = rbac

    async def request_approval(
        self,
        *,
        request_id: str,
        resource_type: str,
        resource_id: str,
        requested_by: str,
        tenant_id: str,
        correlation_id: str,
        reason: Optional[str] = None,
    ) -> ApprovalRequest:
        """Create pending approval request. No auto-approve."""
        request = ApprovalRequest(
            request_id=request_id,
            resource_type=resource_type,
            resource_id=resource_id,
            requested_by=requested_by,
            status=ApprovalStatus.PENDING,
            created_at=datetime.now(timezone.utc),
            decided_by=None,
            decided_at=None,
            reason=reason,
        )
        await self._repo.save(request)
        await self._audit.log_action(
            actor=requested_by,
            tenant_id=tenant_id,
            action="approval_requested",
            resource_type=resource_type,
            resource_id=resource_id,
            reason=reason,
            correlation_id=correlation_id,
            metadata={"request_id": request_id},
        )
        return request

    async def approve(
        self,
        *,
        request_id: str,
        approver_role: Role,
        approver_id: str,
        tenant_id: str,
        correlation_id: str,
        reason: Optional[str] = None,
    ) -> ApprovalRequest:
        """Approve request. Enforce RBAC (only APPROVER or ADMIN). Audit trail."""
        self._rbac.check_permission(approver_role, "approve")
        request = await self._repo.get(request_id)
        if request is None:
            raise InvalidWorkflowStateError(f"Approval request not found: {request_id}")
        if request.status != ApprovalStatus.PENDING:
            raise InvalidWorkflowStateError(
                f"Request not pending: {request_id} (status={request.status.value})"
            )
        approved = ApprovalRequest(
            request_id=request.request_id,
            resource_type=request.resource_type,
            resource_id=request.resource_id,
            requested_by=request.requested_by,
            status=ApprovalStatus.APPROVED,
            created_at=request.created_at,
            decided_by=approver_id,
            decided_at=datetime.now(timezone.utc),
            reason=reason,
        )
        await self._repo.save(approved)
        await self._audit.log_action(
            actor=approver_id,
            tenant_id=tenant_id,
            action="approval_approved",
            resource_type=request.resource_type,
            resource_id=request.resource_id,
            reason=reason,
            correlation_id=correlation_id,
            metadata={"request_id": request_id},
        )
        return approved

    async def reject(
        self,
        *,
        request_id: str,
        rejector_role: Role,
        rejector_id: str,
        tenant_id: str,
        correlation_id: str,
        reason: Optional[str] = None,
    ) -> ApprovalRequest:
        """Reject request. Enforce RBAC. Audit trail."""
        self._rbac.check_permission(
            rejector_role, "approve"
        )  # same permission to reject
        request = await self._repo.get(request_id)
        if request is None:
            raise InvalidWorkflowStateError(f"Approval request not found: {request_id}")
        if request.status != ApprovalStatus.PENDING:
            raise InvalidWorkflowStateError(
                f"Request not pending: {request_id} (status={request.status.value})"
            )
        rejected = ApprovalRequest(
            request_id=request.request_id,
            resource_type=request.resource_type,
            resource_id=request.resource_id,
            requested_by=request.requested_by,
            status=ApprovalStatus.REJECTED,
            created_at=request.created_at,
            decided_by=rejector_id,
            decided_at=datetime.now(timezone.utc),
            reason=reason,
        )
        await self._repo.save(rejected)
        await self._audit.log_action(
            actor=rejector_id,
            tenant_id=tenant_id,
            action="approval_rejected",
            resource_type=request.resource_type,
            resource_id=request.resource_id,
            reason=reason,
            correlation_id=correlation_id,
            metadata={"request_id": request_id},
        )
        return rejected
