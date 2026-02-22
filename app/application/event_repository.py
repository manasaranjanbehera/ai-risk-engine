"""Event repository protocol. Application layer depends on this; infrastructure implements it."""

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Optional, Protocol

from app.domain.models.event import BaseEvent, EventStatus


@dataclass(frozen=True)
class PersistedEvent:
    """Result of persisting an event. Status is RECEIVED at application boundary."""

    event_id: str
    tenant_id: str
    correlation_id: str
    status: EventStatus
    created_at: datetime
    metadata: Optional[Dict[str, Any]] = None
    version: str = "1.0"


class EventRepository(Protocol):
    """Protocol for persisting and retrieving domain events. DB is primary source of truth."""

    async def save(
        self,
        event: BaseEvent,
        correlation_id: str,
    ) -> PersistedEvent:
        """Persist event with status RECEIVED, tenant_id, correlation_id. Returns persisted model with ID."""
        ...

    async def get(self, tenant_id: str, event_id: str) -> Optional[PersistedEvent]:
        """Return persisted event by tenant and event id, or None if not found."""
        ...
