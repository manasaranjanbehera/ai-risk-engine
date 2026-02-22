"""Fixtures for workflow tests."""

from unittest.mock import AsyncMock

import pytest

from app.governance.audit_logger import AuditLogger
from app.workflows.langgraph.state_models import ComplianceState, RiskState


def _base_risk_state(
    event_id: str = "evt-1",
    tenant_id: str = "t1",
    correlation_id: str = "corr-1",
    raw_event: dict | None = None,
) -> RiskState:
    return RiskState(
        event_id=event_id,
        tenant_id=tenant_id,
        correlation_id=correlation_id,
        raw_event=raw_event or {"event_type": "standard"},
        model_version="simulated@1",
        prompt_version=1,
        audit_trail=[],
    )


def _base_compliance_state(
    event_id: str = "evt-1",
    tenant_id: str = "t1",
    correlation_id: str = "corr-1",
    raw_event: dict | None = None,
    regulatory_flags: list | None = None,
) -> ComplianceState:
    return ComplianceState(
        event_id=event_id,
        tenant_id=tenant_id,
        correlation_id=correlation_id,
        raw_event=raw_event or {"event_type": "standard"},
        regulatory_flags=regulatory_flags or [],
        model_version="simulated@1",
        prompt_version=1,
        audit_trail=[],
    )


@pytest.fixture
def audit_repository():
    repo = AsyncMock()
    repo.save = AsyncMock(return_value=None)
    return repo


@pytest.fixture
def audit_logger(audit_repository):
    return AuditLogger(repository=audit_repository)


@pytest.fixture
def risk_state():
    return _base_risk_state()


@pytest.fixture
def compliance_state():
    return _base_compliance_state()
