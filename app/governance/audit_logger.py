"""Immutable audit logging for regulated traceability. No FastAPI."""

from datetime import datetime, timezone

from app.governance.audit_models import AuditRecord
from app.governance.audit_repository import AuditRepository


class AuditLogger:
    """
    Writes immutable audit records via repository.
    Must include: who, what, when (UTC), why, correlation_id.
    Must NOT allow mutation. Logs structured JSON.
    """

    def __init__(self, repository: AuditRepository) -> None:
        self._repository = repository

    async def log_action(
        self,
        *,
        actor: str,
        tenant_id: str,
        action: str,
        resource_type: str,
        resource_id: str,
        reason: str | None,
        correlation_id: str,
        metadata: dict | None,
    ) -> None:
        """Write immutable audit record. Timestamp is UTC."""
        record = AuditRecord(
            actor=actor,
            tenant_id=tenant_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            reason=reason,
            correlation_id=correlation_id,
            metadata=metadata,
            timestamp_utc=datetime.now(timezone.utc),
        )
        await self._repository.save(record)  # Structured JSON stored via repository
