"""Unit tests for EventService.create_event: happy path, idempotency, failures."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.application.event_repository import PersistedEvent
from app.application.event_service import EventService
from app.application.exceptions import MessagingFailureError
from app.domain.models.event import EventStatus, RiskEvent


def _risk_event(
    event_id: str = "evt-123",
    tenant_id: str = "tenant-1",
    status: EventStatus = EventStatus.CREATED,
) -> RiskEvent:
    return RiskEvent(
        event_id=event_id,
        tenant_id=tenant_id,
        status=status,
        created_at=datetime.now(timezone.utc),
        metadata={"version": "1.0"},
        risk_score=50.0,
        category="fraud",
    )


def _persisted(
    event_id: str = "evt-123", tenant_id: str = "tenant-1"
) -> PersistedEvent:
    return PersistedEvent(
        event_id=event_id,
        tenant_id=tenant_id,
        correlation_id="corr-1",
        status=EventStatus.RECEIVED,
        created_at=datetime.now(timezone.utc),
        metadata={"version": "1.0"},
        version="1.0",
    )


@pytest.fixture
def repository():
    r = AsyncMock()
    r.save = AsyncMock(return_value=_persisted())
    return r


@pytest.fixture
def publisher():
    p = AsyncMock()
    p.publish = AsyncMock(return_value=None)
    return p


@pytest.fixture
def redis_client():
    r = AsyncMock()
    r.get_cache = AsyncMock(return_value=None)
    r.set_cache = AsyncMock(return_value=None)
    return r


@pytest.fixture
def workflow_trigger():
    w = AsyncMock()
    w.start = AsyncMock(return_value=None)
    return w


@pytest.fixture
def logger():
    return MagicMock()


@pytest.fixture
def event_service(repository, publisher, redis_client, workflow_trigger, logger):
    return EventService(
        repository=repository,
        publisher=publisher,
        redis_client=redis_client,
        workflow_trigger=workflow_trigger,
        logger=logger,
    )


# ---------- 1. Happy path ----------


async def test_create_event_happy_path(
    event_service,
    repository,
    publisher,
    redis_client,
    workflow_trigger,
    logger,
):
    """No idempotency key exists; event persisted, published, workflow triggered, audit logged, Redis cached."""
    event = _risk_event()
    redis_client.get_cache.return_value = None

    response = await event_service.create_event(
        event=event,
        tenant_id="tenant-1",
        idempotency_key="key-1",
        correlation_id="corr-1",
    )

    assert response.event_id == "evt-123"
    assert response.tenant_id == "tenant-1"
    assert response.status == EventStatus.RECEIVED
    assert response.version == "1.0"

    repository.save.assert_awaited_once()
    publisher.publish.assert_awaited_once()
    workflow_trigger.start.assert_awaited_once_with(
        event_id="evt-123", tenant_id="tenant-1"
    )
    redis_client.set_cache.assert_awaited_once()
    assert logger.info.call_count >= 1


# ---------- 2. Idempotent replay ----------


async def test_create_event_idempotent_replay_returns_cached(
    event_service,
    repository,
    publisher,
    redis_client,
    workflow_trigger,
):
    """Redis key exists; return cached response; repository, publisher, workflow NOT called."""
    from app.domain.schemas.event import EventResponse

    cached = EventResponse(
        event_id="cached-id",
        tenant_id="tenant-1",
        status=EventStatus.RECEIVED,
        created_at=datetime.now(timezone.utc),
        metadata={},
        version="1.0",
    )
    redis_client.get_cache.return_value = cached.model_dump_json()

    response = await event_service.create_event(
        event=_risk_event(),
        tenant_id="tenant-1",
        idempotency_key="key-1",
        correlation_id="corr-1",
    )

    assert response.event_id == "cached-id"
    repository.save.assert_not_awaited()
    publisher.publish.assert_not_awaited()
    workflow_trigger.start.assert_not_awaited()
    redis_client.set_cache.assert_not_awaited()


# ---------- 3. Messaging failure ----------


async def test_create_event_messaging_failure_raises_and_does_not_cache(
    event_service,
    repository,
    publisher,
    redis_client,
):
    """Repository save succeeds; publisher throws; idempotency NOT cached; MessagingFailureError raised."""
    publisher.publish.side_effect = Exception("Broker down")

    with pytest.raises(MessagingFailureError) as exc_info:
        await event_service.create_event(
            event=_risk_event(),
            tenant_id="tenant-1",
            idempotency_key="key-1",
            correlation_id="corr-1",
        )

    assert "Broker down" in str(exc_info.value.message)
    repository.save.assert_awaited_once()
    redis_client.set_cache.assert_not_awaited()


# ---------- 4. Repository failure ----------


async def test_create_event_repository_failure_publisher_and_workflow_not_called(
    event_service,
    repository,
    publisher,
    workflow_trigger,
):
    """Save throws; publisher and workflow NOT called."""
    repository.save.side_effect = Exception("DB error")

    with pytest.raises(Exception) as exc_info:
        await event_service.create_event(
            event=_risk_event(),
            tenant_id="tenant-1",
            idempotency_key="key-1",
            correlation_id="corr-1",
        )

    assert "DB error" in str(exc_info.value)
    publisher.publish.assert_not_awaited()
    workflow_trigger.start.assert_not_awaited()


# ---------- 5. Workflow failure does not fail transaction ----------


async def test_create_event_workflow_failure_returns_success(
    event_service,
    repository,
    publisher,
    redis_client,
    workflow_trigger,
):
    """Workflow fails; log error but return success; idempotency cached."""
    workflow_trigger.start.side_effect = Exception("Workflow error")

    response = await event_service.create_event(
        event=_risk_event(),
        tenant_id="tenant-1",
        idempotency_key="key-1",
        correlation_id="corr-1",
    )

    assert response.event_id == "evt-123"
    assert response.status == EventStatus.RECEIVED
    repository.save.assert_awaited_once()
    publisher.publish.assert_awaited_once()
    workflow_trigger.start.assert_awaited_once()
    redis_client.set_cache.assert_awaited_once()
