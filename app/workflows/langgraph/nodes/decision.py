"""Decision node: final decision APPROVED or REQUIRE_APPROVAL based on policy and risk."""

import logging
import time
from datetime import datetime, timezone

from app.governance.audit_logger import AuditLogger
from app.workflows.langgraph.state_models import RiskState

logger = logging.getLogger(__name__)

WORKFLOW_ACTOR = "workflow"
HIGH_RISK_THRESHOLD = 75.0


async def make_decision(
    state: RiskState,
    *,
    audit_logger: AuditLogger,
) -> RiskState:
    """
    Final decision: REQUIRE_APPROVAL if policy fail or high risk or guardrail violation; else APPROVED.
    Deterministic. Emits audit "decision_made".
    """
    start = time.perf_counter()
    policy_fail = state.policy_result == "FAIL"
    high_risk = (state.risk_score or 0.0) >= HIGH_RISK_THRESHOLD
    guardrail_violation = state.guardrail_result == "VIOLATION"
    if policy_fail or high_risk or guardrail_violation:
        final_decision = "REQUIRE_APPROVAL"
    else:
        final_decision = "APPROVED"
    elapsed_ms = (time.perf_counter() - start) * 1000

    trail_entry = {
        "node": "decision",
        "action": "decision_made",
        "at": datetime.now(timezone.utc).isoformat(),
        "model_version": state.model_version,
        "prompt_version": state.prompt_version,
        "execution_ms": round(elapsed_ms, 2),
        "final_decision": final_decision,
    }
    new_trail = list(state.audit_trail) + [trail_entry]

    await audit_logger.log_action(
        actor=WORKFLOW_ACTOR,
        tenant_id=state.tenant_id,
        action="decision_made",
        resource_type="workflow",
        resource_id=state.event_id,
        reason="deterministic_decision",
        correlation_id=state.correlation_id,
        metadata={
            "model_version": state.model_version,
            "prompt_version": state.prompt_version,
            "execution_ms": round(elapsed_ms, 2),
            "final_decision": final_decision,
        },
    )
    logger.info(
        "decision_node_completed",
        extra={
            "event_id": state.event_id,
            "final_decision": final_decision,
            "model_version": state.model_version,
        },
    )
    return state.transition(
        final_decision=final_decision,
        audit_trail=new_trail,
    )
