"""Retrieval node: simulate vector retrieval, add retrieved_context, emit audit."""

import logging
import time
from datetime import datetime, timezone

from app.governance.audit_logger import AuditLogger
from app.workflows.langgraph.state_models import RiskState

logger = logging.getLogger(__name__)

WORKFLOW_ACTOR = "workflow"


async def retrieve_context(
    state: RiskState,
    *,
    audit_logger: AuditLogger,
) -> RiskState:
    """
    Simulate vector retrieval. Adds retrieved_context to state.
    Deterministic: no randomness. Emits audit event "context_retrieved".
    """
    start = time.perf_counter()
    # Simulate deterministic context from raw_event (e.g. event_type + tenant)
    raw = state.raw_event or {}
    event_type = raw.get("event_type", "unknown")
    context = f"simulated_context:{state.tenant_id}:{event_type}"
    elapsed_ms = (time.perf_counter() - start) * 1000

    trail_entry = {
        "node": "retrieval",
        "action": "context_retrieved",
        "at": datetime.now(timezone.utc).isoformat(),
        "model_version": state.model_version,
        "prompt_version": state.prompt_version,
        "execution_ms": round(elapsed_ms, 2),
    }
    new_trail = list(state.audit_trail) + [trail_entry]

    await audit_logger.log_action(
        actor=WORKFLOW_ACTOR,
        tenant_id=state.tenant_id,
        action="context_retrieved",
        resource_type="workflow",
        resource_id=state.event_id,
        reason="vector_retrieval_simulated",
        correlation_id=state.correlation_id,
        metadata={
            "model_version": state.model_version,
            "prompt_version": state.prompt_version,
            "execution_ms": round(elapsed_ms, 2),
        },
    )
    logger.info(
        "retrieval_node_completed",
        extra={
            "event_id": state.event_id,
            "correlation_id": state.correlation_id,
            "model_version": state.model_version,
            "prompt_version": state.prompt_version,
            "execution_ms": round(elapsed_ms, 2),
        },
    )
    return state.transition(
        retrieved_context=context,
        audit_trail=new_trail,
    )
