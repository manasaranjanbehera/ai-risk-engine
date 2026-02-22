"""Policy validation node: simulate rule-based validation, set policy_result PASS/FAIL."""

import logging
import time
from datetime import datetime, timezone

from app.governance.audit_logger import AuditLogger
from app.workflows.langgraph.state_models import RiskState

logger = logging.getLogger(__name__)

WORKFLOW_ACTOR = "workflow"


async def validate_policy(
    state: RiskState,
    *,
    audit_logger: AuditLogger,
) -> RiskState:
    """
    Simulate rule-based policy validation. Sets policy_result to PASS or FAIL.
    Deterministic: e.g. FAIL if raw_event has policy_override flag or high-risk category.
    Emits audit. If FAIL, downstream decision node will mark REQUIRE_APPROVAL.
    """
    start = time.perf_counter()
    raw = state.raw_event or {}
    # Deterministic: fail if metadata has "policy_override" or category is "sensitive"
    category = (raw.get("metadata") or {}).get("category", "")
    policy_override = (raw.get("metadata") or {}).get("policy_override", False)
    if policy_override or category == "sensitive":
        policy_result = "FAIL"
    else:
        policy_result = "PASS"
    elapsed_ms = (time.perf_counter() - start) * 1000

    trail_entry = {
        "node": "policy_validation",
        "action": "policy_validated",
        "at": datetime.now(timezone.utc).isoformat(),
        "model_version": state.model_version,
        "prompt_version": state.prompt_version,
        "execution_ms": round(elapsed_ms, 2),
        "policy_result": policy_result,
    }
    new_trail = list(state.audit_trail) + [trail_entry]

    await audit_logger.log_action(
        actor=WORKFLOW_ACTOR,
        tenant_id=state.tenant_id,
        action="policy_validated",
        resource_type="workflow",
        resource_id=state.event_id,
        reason="rule_based_validation",
        correlation_id=state.correlation_id,
        metadata={
            "model_version": state.model_version,
            "prompt_version": state.prompt_version,
            "execution_ms": round(elapsed_ms, 2),
            "policy_result": policy_result,
        },
    )
    logger.info(
        "policy_validation_node_completed",
        extra={
            "event_id": state.event_id,
            "policy_result": policy_result,
            "model_version": state.model_version,
            "prompt_version": state.prompt_version,
        },
    )
    return state.transition(
        policy_result=policy_result,
        audit_trail=new_trail,
    )
