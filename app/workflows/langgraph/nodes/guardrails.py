"""Guardrails node: threshold enforcement and blocked patterns. Escalate on violation."""

import logging
import time
from datetime import datetime, timezone

from app.governance.audit_logger import AuditLogger
from app.workflows.langgraph.state_models import RiskState

logger = logging.getLogger(__name__)

WORKFLOW_ACTOR = "workflow"
HIGH_RISK_THRESHOLD = 75.0


async def apply_guardrails(
    state: RiskState,
    *,
    audit_logger: AuditLogger,
) -> RiskState:
    """
    Simulate guardrails: threshold enforcement and blocked patterns.
    If risk_score >= threshold or blocked pattern in raw_event -> VIOLATION, else OK.
    Violation leads to escalation (decision node will set REQUIRE_APPROVAL).
    """
    start = time.perf_counter()
    raw = state.raw_event or {}
    risk_score = state.risk_score or 0.0
    metadata = raw.get("metadata") or {}
    blocked = metadata.get("blocked_pattern", False)
    over_threshold = risk_score >= HIGH_RISK_THRESHOLD
    if blocked or over_threshold:
        guardrail_result = "VIOLATION"
    else:
        guardrail_result = "OK"
    elapsed_ms = (time.perf_counter() - start) * 1000

    trail_entry = {
        "node": "guardrails",
        "action": "guardrails_applied",
        "at": datetime.now(timezone.utc).isoformat(),
        "model_version": state.model_version,
        "prompt_version": state.prompt_version,
        "execution_ms": round(elapsed_ms, 2),
        "guardrail_result": guardrail_result,
    }
    new_trail = list(state.audit_trail) + [trail_entry]

    await audit_logger.log_action(
        actor=WORKFLOW_ACTOR,
        tenant_id=state.tenant_id,
        action="guardrails_applied",
        resource_type="workflow",
        resource_id=state.event_id,
        reason="threshold_and_pattern_check",
        correlation_id=state.correlation_id,
        metadata={
            "model_version": state.model_version,
            "prompt_version": state.prompt_version,
            "execution_ms": round(elapsed_ms, 2),
            "guardrail_result": guardrail_result,
        },
    )
    logger.info(
        "guardrails_node_completed",
        extra={
            "event_id": state.event_id,
            "guardrail_result": guardrail_result,
            "model_version": state.model_version,
        },
    )
    return state.transition(
        guardrail_result=guardrail_result,
        audit_trail=new_trail,
    )
