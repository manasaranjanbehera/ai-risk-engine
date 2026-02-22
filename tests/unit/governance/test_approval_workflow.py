"""Governance tests: approval workflow enforces RBAC; status transitions enforced."""

from unittest.mock import AsyncMock

import pytest

from app.governance.approval_workflow import (
    ApprovalRequest,
    ApprovalStatus,
    ApprovalWorkflow,
)
from app.governance.exceptions import InvalidWorkflowStateError
from app.security.exceptions import AuthorizationError
from app.security.rbac import RBACService, Role


@pytest.fixture
def approval_repo():
    store: dict[str, ApprovalRequest] = {}

    async def save(r: ApprovalRequest) -> None:
        store[r.request_id] = r

    async def get(rid: str):
        return store.get(rid)

    repo = AsyncMock()
    repo.save = save
    repo.get = get
    return repo


@pytest.fixture
def audit_logger():
    a = AsyncMock()
    a.log_action = AsyncMock(return_value=None)
    return a


@pytest.fixture
def rbac():
    return RBACService()


@pytest.fixture
def approval_workflow(approval_repo, audit_logger, rbac):
    return ApprovalWorkflow(
        repository=approval_repo,
        audit_logger=audit_logger,
        rbac=rbac,
    )


async def test_approval_workflow_enforces_rbac_approver_can_approve(
    approval_workflow, approval_repo
):
    await approval_workflow.request_approval(
        request_id="req-1",
        resource_type="model",
        resource_id="m1@1",
        requested_by="user1",
        tenant_id="t1",
        correlation_id="c1",
    )
    approved = await approval_workflow.approve(
        request_id="req-1",
        approver_role=Role.APPROVER,
        approver_id="approver-1",
        tenant_id="t1",
        correlation_id="c1",
    )
    assert approved.status == ApprovalStatus.APPROVED


async def test_approval_workflow_enforces_rbac_analyst_cannot_approve(
    approval_workflow, approval_repo
):
    await approval_workflow.request_approval(
        request_id="req-1",
        resource_type="model",
        resource_id="m1@1",
        requested_by="user1",
        tenant_id="t1",
        correlation_id="c1",
    )
    with pytest.raises(AuthorizationError) as exc_info:
        await approval_workflow.approve(
            request_id="req-1",
            approver_role=Role.ANALYST,
            approver_id="analyst-1",
            tenant_id="t1",
            correlation_id="c1",
        )
    assert "approve" in str(exc_info.value.message).lower()


async def test_approval_workflow_enforces_rbac_viewer_cannot_approve(
    approval_workflow, approval_repo
):
    await approval_workflow.request_approval(
        request_id="req-1",
        resource_type="model",
        resource_id="m1@1",
        requested_by="user1",
        tenant_id="t1",
        correlation_id="c1",
    )
    with pytest.raises(AuthorizationError):
        await approval_workflow.approve(
            request_id="req-1",
            approver_role=Role.VIEWER,
            approver_id="viewer-1",
            tenant_id="t1",
            correlation_id="c1",
        )


async def test_status_transitions_enforced_cannot_approve_non_pending(
    approval_workflow, approval_repo
):
    await approval_workflow.request_approval(
        request_id="req-1",
        resource_type="model",
        resource_id="m1@1",
        requested_by="user1",
        tenant_id="t1",
        correlation_id="c1",
    )
    await approval_workflow.approve(
        request_id="req-1",
        approver_role=Role.ADMIN,
        approver_id="admin",
        tenant_id="t1",
        correlation_id="c1",
    )
    with pytest.raises(InvalidWorkflowStateError) as exc_info:
        await approval_workflow.approve(
            request_id="req-1",
            approver_role=Role.ADMIN,
            approver_id="admin",
            tenant_id="t1",
            correlation_id="c2",
        )
    assert "not pending" in str(exc_info.value.message).lower()


async def test_reject_enforces_rbac(approval_workflow, approval_repo):
    await approval_workflow.request_approval(
        request_id="req-1",
        resource_type="model",
        resource_id="m1@1",
        requested_by="user1",
        tenant_id="t1",
        correlation_id="c1",
    )
    with pytest.raises(AuthorizationError):
        await approval_workflow.reject(
            request_id="req-1",
            rejector_role=Role.VIEWER,
            rejector_id="v1",
            tenant_id="t1",
            correlation_id="c1",
        )
