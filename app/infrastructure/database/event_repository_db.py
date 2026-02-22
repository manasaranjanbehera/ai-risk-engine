"""DB-backed event repository. Persists events to PostgreSQL (events table)."""

from datetime import datetime
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.event_repository import PersistedEvent
from app.domain.models.event import BaseEvent, EventStatus
from app.infrastructure.database.models import Event


class DbEventRepository:
    """Persists domain events to PostgreSQL with status RECEIVED. Implements EventRepository protocol."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(
        self,
        event: BaseEvent,
        correlation_id: str,
    ) -> PersistedEvent:
        """Store event with status RECEIVED; commit and return PersistedEvent."""
        version = "1.0"
        if event.metadata and isinstance(event.metadata.get("version"), str):
            version = event.metadata["version"]
        event_type = type(event).__name__
        orm = Event(
            event_id=event.event_id,
            tenant_id=event.tenant_id,
            correlation_id=correlation_id,
            status=EventStatus.RECEIVED.value,
            event_type=event_type,
            metadata_=event.metadata,
            version=version,
        )
        self._session.add(orm)
        await self._session.flush()
        await self._session.commit()
        await self._session.refresh(orm)
        created_at = orm.created_at
        if created_at and created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=datetime.now().astimezone().tzinfo)
        return PersistedEvent(
            event_id=orm.event_id,
            tenant_id=orm.tenant_id,
            correlation_id=orm.correlation_id,
            status=EventStatus.RECEIVED,
            created_at=created_at or event.created_at,
            metadata=event.metadata,
            version=version,
        )

    async def get(self, tenant_id: str, event_id: str) -> Optional[PersistedEvent]:
        """Return persisted event by tenant_id and event_id, or None."""
        stmt = select(Event).where(
            Event.tenant_id == tenant_id,
            Event.event_id == event_id,
            Event.is_deleted.is_(False),
        )
        result = await self._session.execute(stmt)
        orm = result.scalar_one_or_none()
        if orm is None:
            return None
        created_at = orm.created_at
        if created_at and created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=datetime.now().astimezone().tzinfo)
        return PersistedEvent(
            event_id=orm.event_id,
            tenant_id=orm.tenant_id,
            correlation_id=orm.correlation_id,
            status=EventStatus(orm.status),
            created_at=created_at,
            metadata=orm.metadata_,
            version=orm.version or "1.0",
        )
