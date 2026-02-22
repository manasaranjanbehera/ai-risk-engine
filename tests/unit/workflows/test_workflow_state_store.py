"""Workflow state store tests: serialization roundtrip, get/set."""

from unittest.mock import AsyncMock

import pytest

from app.workflows.langgraph.state_models import RiskState
from app.workflows.langgraph.workflow_state_store import (
    _risk_state_from_json,
    _risk_state_to_json,
    RedisWorkflowStateStore,
)


def test_risk_state_serialization_roundtrip():
    """Store module serialize/deserialize must roundtrip RiskState."""
    state = RiskState(
        event_id="e1",
        tenant_id="t1",
        correlation_id="c1",
        raw_event={"a": 1},
        risk_score=50.0,
        audit_trail=[{"node": "retrieval"}],
    )
    data = _risk_state_to_json(state)
    restored = _risk_state_from_json(data)
    assert restored.event_id == state.event_id
    assert restored.risk_score == state.risk_score
    assert restored.audit_trail == state.audit_trail


@pytest.mark.asyncio
async def test_redis_workflow_state_store_get_miss():
    """get_risk_state returns None when key not in Redis."""
    redis = AsyncMock()
    redis.get_cache = AsyncMock(return_value=None)
    store = RedisWorkflowStateStore(redis)
    out = await store.get_risk_state("evt-1")
    assert out is None
    redis.get_cache.assert_awaited_once_with("workflow:evt-1")


@pytest.mark.asyncio
async def test_redis_workflow_state_store_set_then_get():
    """set_risk_state then get_risk_state returns same state."""
    redis = AsyncMock()
    redis.get_cache = AsyncMock(return_value=None)
    redis.set_cache = AsyncMock(return_value=None)
    store = RedisWorkflowStateStore(redis)
    state = RiskState(
        event_id="evt-1",
        tenant_id="t1",
        correlation_id="c1",
        final_decision="APPROVED",
    )
    await store.set_risk_state("evt-1", state, ttl_seconds=600)
    redis.set_cache.assert_awaited_once()
    call = redis.set_cache.call_args
    assert call[0][0] == "workflow:evt-1"
    restored = _risk_state_from_json(call[0][1])
    assert restored.event_id == state.event_id
    assert restored.final_decision == state.final_decision
