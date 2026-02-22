"""Workflow state store for idempotency: cache state by event_id. Protocol + Redis implementation."""

from typing import Protocol

from app.workflows.langgraph.state_models import ComplianceState, RiskState


class WorkflowStateStore(Protocol):
    """Storage for workflow state snapshot. Key: workflow:{event_id}. Used for idempotency."""

    async def get_risk_state(self, event_id: str) -> RiskState | None:
        """Return cached risk state if exists; otherwise None."""
        ...

    async def set_risk_state(
        self, event_id: str, state: RiskState, ttl_seconds: int = 3600
    ) -> None:
        """Store risk state. Prevent double execution when key exists."""
        ...


class ComplianceStateStore(Protocol):
    """Storage for compliance workflow state. Key: workflow:compliance:{event_id}."""

    async def get_compliance_state(self, event_id: str) -> ComplianceState | None: ...

    async def set_compliance_state(
        self, event_id: str, state: ComplianceState, ttl_seconds: int = 3600
    ) -> None: ...


def _risk_state_to_json(state: RiskState) -> str:
    """Serialize RiskState to JSON string."""
    return state.model_dump_json()


def _risk_state_from_json(data: str) -> RiskState:
    """Deserialize JSON string to RiskState."""
    return RiskState.model_validate_json(data)


def _compliance_state_to_json(state: ComplianceState) -> str:
    return state.model_dump_json()


def _compliance_state_from_json(data: str) -> ComplianceState:
    return ComplianceState.model_validate_json(data)


class RedisWorkflowStateStore:
    """Store workflow state in Redis. Key pattern: workflow:{event_id}."""

    def __init__(self, redis_client: object, key_prefix: str = "workflow") -> None:
        self._redis = redis_client
        self._prefix = key_prefix

    def _key(self, event_id: str) -> str:
        return f"{self._prefix}:{event_id}"

    def _compliance_key(self, event_id: str) -> str:
        return f"{self._prefix}:compliance:{event_id}"

    async def get_risk_state(self, event_id: str) -> RiskState | None:
        raw = await self._redis.get_cache(self._key(event_id))  # type: ignore[union-attr]
        if raw is None:
            return None
        return _risk_state_from_json(raw)

    async def set_risk_state(
        self, event_id: str, state: RiskState, ttl_seconds: int = 3600
    ) -> None:
        await self._redis.set_cache(  # type: ignore[union-attr]
            self._key(event_id), _risk_state_to_json(state), ttl=ttl_seconds
        )

    async def get_compliance_state(self, event_id: str) -> ComplianceState | None:
        raw = await self._redis.get_cache(self._compliance_key(event_id))  # type: ignore[union-attr]
        if raw is None:
            return None
        return _compliance_state_from_json(raw)

    async def set_compliance_state(
        self, event_id: str, state: ComplianceState, ttl_seconds: int = 3600
    ) -> None:
        await self._redis.set_cache(  # type: ignore[union-attr]
            self._compliance_key(event_id),
            _compliance_state_to_json(state),
            ttl=ttl_seconds,
        )
