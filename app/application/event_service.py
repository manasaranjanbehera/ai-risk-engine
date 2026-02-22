"""Event application service — transaction boundary. Orchestrates persist, publish, workflow, audit."""

import logging
from typing import Optional

from app.application.event_repository import EventRepository, PersistedEvent
from app.application.exceptions import MessagingFailureError
from app.domain.models.event import BaseEvent, ComplianceEvent, EventStatus, RiskEvent
from app.domain.schemas.event import EventResponse
from app.infrastructure.cache.redis_client import RedisClient
from app.infrastructure.messaging.rabbitmq_publisher import RabbitMQPublisher
from app.workflows.interface import WorkflowTrigger

IDEMPOTENCY_PREFIX = "idempotency:"
IDEMPOTENCY_TTL = 300  # 5 minutes
EXCHANGE_RISK_EVENTS = "risk_events"
ROUTING_RISK_CREATED = "risk.created"
ROUTING_COMPLIANCE_CREATED = "compliance.created"


def _idempotency_key(tenant_id: str, idempotency_key: str) -> str:
    return f"{IDEMPOTENCY_PREFIX}{tenant_id}:{idempotency_key}"


def _routing_key(event: BaseEvent) -> str:
    if isinstance(event, RiskEvent):
        return ROUTING_RISK_CREATED
    if isinstance(event, ComplianceEvent):
        return ROUTING_COMPLIANCE_CREATED
    return "event.created"


def _event_type_name(event: BaseEvent) -> str:
    return type(event).__name__


def _persisted_to_response(p: PersistedEvent) -> EventResponse:
    return EventResponse(
        event_id=p.event_id,
        tenant_id=p.tenant_id,
        status=p.status,
        created_at=p.created_at,
        metadata=p.metadata,
        version=p.version,
    )


class EventService:
    """
    Application-layer orchestration only. No HTTP, no FastAPI, no direct infrastructure.
    Transaction strategy: DB persistence is primary; messaging failure breaks transaction;
    workflow failure does not (log and return success).
    """

    def __init__(
        self,
        repository: EventRepository,
        publisher: RabbitMQPublisher,
        redis_client: RedisClient,
        workflow_trigger: WorkflowTrigger,
        logger: logging.Logger,
    ) -> None:
        self._repository = repository
        self._publisher = publisher
        self._redis = redis_client
        self._workflow_trigger = workflow_trigger
        self._logger = logger

    async def create_event(
        self,
        event: BaseEvent,
        tenant_id: str,
        idempotency_key: str,
        correlation_id: str,
    ) -> EventResponse:
        """
        Single entry point: idempotent create. Enforces idempotency, persists, publishes,
        triggers workflow (best-effort), audits, caches response, returns EventResponse.
        """
        cache_key = _idempotency_key(tenant_id, idempotency_key)

        # Step 1 — Idempotency enforcement
        self._logger.info(
            "idempotency_check",
            extra={"tenant_id": tenant_id, "correlation_id": correlation_id},
        )
        cached = await self._redis.get_cache(cache_key)
        if cached:
            self._logger.info(
                "idempotent_replay",
                extra={"tenant_id": tenant_id, "correlation_id": correlation_id},
            )
            return EventResponse.model_validate_json(cached)

        # Step 2 — Persist event (primary source of truth)
        self._logger.info(
            "event_persisted",
            extra={"tenant_id": tenant_id, "correlation_id": correlation_id},
        )
        persisted = await self._repository.save(event, correlation_id)

        # Step 3 — Publish to RabbitMQ (secondary; failure = transaction failure, do not cache)
        message = {
            "event_id": persisted.event_id,
            "tenant_id": persisted.tenant_id,
            "correlation_id": persisted.correlation_id,
            "event_type": _event_type_name(event),
            "status": persisted.status.value,
        }
        try:
            await self._publisher.publish(
                EXCHANGE_RISK_EVENTS,
                _routing_key(event),
                message,
                idempotency_key,
            )
        except Exception as e:
            self._logger.error(
                "event_creation_failed",
                extra={
                    "tenant_id": tenant_id,
                    "correlation_id": correlation_id,
                    "event_id": persisted.event_id,
                    "error": str(e),
                },
            )
            raise MessagingFailureError(f"Publish failed: {e}") from e
        self._logger.info(
            "event_published",
            extra={
                "tenant_id": tenant_id,
                "correlation_id": correlation_id,
                "event_id": persisted.event_id,
            },
        )

        # Step 4 — Trigger workflow (placeholder); failure does NOT break transaction
        try:
            await self._workflow_trigger.start(
                event_id=persisted.event_id,
                tenant_id=persisted.tenant_id,
            )
            self._logger.info(
                "workflow_triggered",
                extra={
                    "tenant_id": persisted.tenant_id,
                    "correlation_id": correlation_id,
                    "event_id": persisted.event_id,
                },
            )
        except Exception as e:
            self._logger.error(
                "workflow_trigger_failed",
                extra={
                    "tenant_id": persisted.tenant_id,
                    "correlation_id": correlation_id,
                    "event_id": persisted.event_id,
                    "error": str(e),
                },
            )
            # Do not re-raise: workflow failure does not fail the transaction.

        # Step 5 — Emit audit log
        self._logger.info(
            "event_created",
            extra={
                "event": "event_created",
                "event_id": persisted.event_id,
                "tenant_id": persisted.tenant_id,
                "correlation_id": correlation_id,
                "event_type": _event_type_name(event),
                "status": EventStatus.RECEIVED.value,
            },
        )

        # Step 6 — Cache idempotency result
        response = _persisted_to_response(persisted)
        await self._redis.set_cache(
            cache_key,
            response.model_dump_json(),
            ttl=IDEMPOTENCY_TTL,
        )
        self._logger.info(
            "idempotency_cached",
            extra={
                "tenant_id": tenant_id,
                "correlation_id": correlation_id,
                "event_id": persisted.event_id,
            },
        )

        # Step 7 — Return EventResponse
        return response

    async def get_event(self, tenant_id: str, event_id: str) -> Optional[EventResponse]:
        """Retrieve event by tenant_id and event_id. Returns EventResponse or None."""
        persisted = await self._repository.get(tenant_id, event_id)
        if persisted is None:
            return None
        return _persisted_to_response(persisted)
