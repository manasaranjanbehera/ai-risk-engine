"""Immutable audit record model. Domain-level immutability."""

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Optional


@dataclass(frozen=True)
class AuditRecord:
    """
    Immutable audit record: who, what, when (UTC), why, correlation_id.
    """

    actor: str
    tenant_id: str
    action: str
    resource_type: str
    resource_id: str
    reason: Optional[str]
    correlation_id: str
    metadata: Optional[Dict[str, Any]]
    timestamp_utc: datetime

    def to_dict(self) -> Dict[str, Any]:
        """Structured representation for JSON logging."""
        return {
            "actor": self.actor,
            "tenant_id": self.tenant_id,
            "action": self.action,
            "resource_type": self.resource_type,
            "resource_id": self.resource_id,
            "reason": self.reason,
            "correlation_id": self.correlation_id,
            "metadata": self.metadata,
            "timestamp_utc": self.timestamp_utc.isoformat(),
        }
