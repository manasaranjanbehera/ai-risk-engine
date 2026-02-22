"""Redis-backed event repository. Persists event with status RECEIVED and returns PersistedEvent."""

import json
from datetime import datetime
from typing import Any, Dict, Optional

from app.application.event_repository import PersistedEvent
from app.domain.models.event import BaseEvent, EventStatus
from app.infrastructure.cache.redis_client import RedisClient

EVENT_STORE_PREFIX = "event:"
EVENT_STORE_TTL = 86400 * 7  # 7 days


class RedisEventRepository:
    """Persists domain events to Redis with status RECEIVED. Implements EventRepository protocol."""

    def __init__(self, redis_client: RedisClient) -> None:
        self._redis = redis_client

    async def save(
        self,
        event: BaseEvent,
        correlation_id: str,
    ) -> PersistedEvent:
        """Store event with status RECEIVED, tenant_id, correlation_id. Returns PersistedEvent."""
        version = "1.0"
        if event.metadata and isinstance(event.metadata.get("version"), str):
            version = event.metadata["version"]
        persisted = PersistedEvent(
            event_id=event.event_id,
            tenant_id=event.tenant_id,
            correlation_id=correlation_id,
            status=EventStatus.RECEIVED,
            created_at=event.created_at,
            metadata=event.metadata,
            version=version,
        )
        payload: Dict[str, Any] = {
            "event_id": persisted.event_id,
            "tenant_id": persisted.tenant_id,
            "correlation_id": persisted.correlation_id,
            "status": persisted.status.value,
            "created_at": persisted.created_at.isoformat(),
            "metadata": persisted.metadata,
            "version": persisted.version,
        }
        key = f"{EVENT_STORE_PREFIX}{event.tenant_id}:{event.event_id}"
        await self._redis.set_cache(key, json.dumps(payload), ttl=EVENT_STORE_TTL)
        return persisted

    async def get(self, tenant_id: str, event_id: str) -> Optional[PersistedEvent]:
        """Return persisted event by tenant and event id from Redis, or None."""
        key = f"{EVENT_STORE_PREFIX}{tenant_id}:{event_id}"
        raw = await self._redis.get_cache(key)
        if not raw:
            return None
        data = json.loads(raw)
        return PersistedEvent(
            event_id=data["event_id"],
            tenant_id=data["tenant_id"],
            correlation_id=data["correlation_id"],
            status=EventStatus(data["status"]),
            created_at=datetime.fromisoformat(
                data["created_at"].replace("Z", "+00:00")
            ),
            metadata=data.get("metadata"),
            version=data.get("version", "1.0"),
        )
