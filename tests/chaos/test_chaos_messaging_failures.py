"""
Chaos: RabbitMQ/messaging failure during publish.
System must: fail gracefully, classify failure, not cache success (audit integrity), preserve idempotency on retry.
"""

import logging
from datetime import datetime
from unittest.mock import AsyncMock

import pytest

from app.application.event_repository import PersistedEvent
from app.application.event_service import EventService
from app.application.exceptions import MessagingFailureError
from app.domain.models.event import EventStatus, RiskEvent


@pytest.mark.asyncio
async def test_messaging_failure_raises_messaging_error():
    """When publisher.publish raises, EventService raises MessagingFailureError."""
    persisted = PersistedEvent(
        event_id="e1",
        tenant_id="t1",
        correlation_id="c1",
        status=EventStatus.RECEIVED,
        created_at=datetime.utcnow(),
        metadata=None,
        version="1.0",
    )
    repo = AsyncMock()
    repo.save = AsyncMock(return_value=persisted)
    publisher = AsyncMock()
    publisher.publish = AsyncMock(side_effect=RuntimeError("connection refused"))
    redis = AsyncMock()
    redis.get_cache = AsyncMock(return_value=None)
    redis.set_cache = AsyncMock(return_value=None)
    redis.set_idempotency_key = AsyncMock(return_value=True)
    workflow_trigger = AsyncMock()
    workflow_trigger.start = AsyncMock(return_value=None)
    logger = logging.getLogger(__name__)
    service = EventService(
        repository=repo,
        publisher=publisher,
        redis_client=redis,
        workflow_trigger=workflow_trigger,
        logger=logger,
    )
    event = RiskEvent(
        event_id="e1",
        tenant_id="t1",
        status=EventStatus.CREATED,
        created_at=datetime.utcnow(),
        metadata=None,
        risk_score=50,
        category="test",
    )
    with pytest.raises(MessagingFailureError):
        await service.create_event(
            event=event,
            tenant_id="t1",
            idempotency_key="key1",
            correlation_id="c1",
        )
    # Idempotency not cached on messaging failure (transaction not completed)
    redis.set_cache.assert_not_called()
