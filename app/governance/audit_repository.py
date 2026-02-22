"""Audit repository protocol. Governance layer depends on this; infrastructure implements it."""

from typing import Protocol

from app.governance.audit_models import AuditRecord


class AuditRepository(Protocol):
    """Protocol for persisting immutable audit records."""

    async def save(self, record: AuditRecord) -> None:
        """Persist an immutable audit record. Must not allow mutation."""
        ...
