"""Governance tests: audit immutability and audit fields completeness."""

from datetime import timezone
from unittest.mock import AsyncMock

import pytest

from app.governance.audit_logger import AuditLogger
from app.governance.audit_models import AuditRecord


@pytest.fixture
def audit_repository():
    repo = AsyncMock()
    repo.save = AsyncMock(return_value=None)
    return repo


@pytest.fixture
def audit_logger(audit_repository):
    return AuditLogger(repository=audit_repository)


async def test_audit_immutability(audit_logger, audit_repository):
    """Audit record must not allow mutation; stored via repository."""
    await audit_logger.log_action(
        actor="user-1",
        tenant_id="t1",
        action="test_action",
        resource_type="event",
        resource_id="evt-1",
        reason="test",
        correlation_id="corr-1",
        metadata={"k": "v"},
    )
    assert audit_repository.save.await_count == 1
    record = audit_repository.save.call_args[0][0]
    assert isinstance(record, AuditRecord)
    assert record.actor == "user-1"
    assert record.tenant_id == "t1"
    assert record.action == "test_action"
    assert record.resource_type == "event"
    assert record.resource_id == "evt-1"
    assert record.reason == "test"
    assert record.correlation_id == "corr-1"
    assert record.metadata == {"k": "v"}
    # Immutability: frozen dataclass
    with pytest.raises(AttributeError):
        record.actor = "other"  # type: ignore[misc]


async def test_audit_fields_completeness(audit_logger, audit_repository):
    """Must include who, what, when (UTC), why, correlation_id."""
    await audit_logger.log_action(
        actor="who",
        tenant_id="t1",
        action="what",
        resource_type="resource",
        resource_id="id-1",
        reason="why",
        correlation_id="corr-id",
        metadata=None,
    )
    record = audit_repository.save.call_args[0][0]
    assert record.actor == "who"
    assert record.action == "what"
    assert record.reason == "why"
    assert record.correlation_id == "corr-id"
    assert record.timestamp_utc.tzinfo == timezone.utc
    d = record.to_dict()
    assert "timestamp_utc" in d
    assert "actor" in d and "action" in d and "reason" in d and "correlation_id" in d
