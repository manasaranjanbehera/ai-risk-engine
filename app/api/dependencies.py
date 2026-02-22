"""FastAPI dependency injection: Redis, Publisher, EventService, tenant, correlation_id."""

import logging
from typing import Annotated

from fastapi import Depends, Request

from app.application.event_service import EventService
from app.infrastructure.cache.redis_client import RedisClient
from app.infrastructure.cache.event_repository_redis import RedisEventRepository
from app.infrastructure.messaging.rabbitmq_publisher import RabbitMQPublisher
from app.workflows.dummy_workflow import DummyWorkflowTrigger

_redis_client: RedisClient | None = None
_publisher: RabbitMQPublisher | None = None


def get_redis_client() -> RedisClient:
    """Return singleton Redis client."""
    global _redis_client
    if _redis_client is None:
        _redis_client = RedisClient()
    return _redis_client


def get_publisher() -> RabbitMQPublisher:
    """Return singleton RabbitMQ publisher."""
    global _publisher
    if _publisher is None:
        _publisher = RabbitMQPublisher()
    return _publisher


async def get_event_service(
    redis: Annotated[RedisClient, Depends(get_redis_client)],
    publisher: Annotated[RabbitMQPublisher, Depends(get_publisher)],
) -> EventService:
    """Build EventService with injected repository, publisher, redis, workflow trigger, logger.
    Uses RedisEventRepository by default. To use DB-backed store, override this dependency
    with a factory that injects DbEventRepository(session) from app.infrastructure.database.event_repository_db.
    Run app/migrations/001_initial_schema.sql to create the events table (and full schema).
    """
    repository = RedisEventRepository(redis_client=redis)
    workflow_trigger = DummyWorkflowTrigger()
    logger = logging.getLogger(__name__)
    return EventService(
        repository=repository,
        publisher=publisher,
        redis_client=redis,
        workflow_trigger=workflow_trigger,
        logger=logger,
    )


def get_tenant_id(request: Request) -> str:
    """Extract tenant_id from request.state (set by middleware)."""
    return request.state.tenant_id


def get_correlation_id(request: Request) -> str:
    """Extract correlation_id from request.state (set by middleware)."""
    return getattr(request.state, "correlation_id", "") or ""
