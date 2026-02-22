"""Compliance workflow nodes: same pipeline as risk but with ComplianceState and compliance decision."""

import logging
import time
from datetime import datetime, timezone

from app.governance.audit_logger import AuditLogger
from app.workflows.langgraph.state_models import ComplianceState

logger = logging.getLogger(__name__)

WORKFLOW_ACTOR = "workflow"
HIGH_RISK_THRESHOLD = 75.0


async def retrieve_context_compliance(
    state: ComplianceState,
    *,
    audit_logger: AuditLogger,
) -> ComplianceState:
    """Simulate vector retrieval for compliance workflow. Deterministic."""
    start = time.perf_counter()
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
    return state.transition(retrieved_context=context, audit_trail=new_trail)


async def validate_policy_compliance(
    state: ComplianceState,
    *,
    audit_logger: AuditLogger,
) -> ComplianceState:
    """Simulate policy validation for compliance. Deterministic."""
    start = time.perf_counter()
    raw = state.raw_event or {}
    category = (raw.get("metadata") or {}).get("category", "")
    policy_override = (raw.get("metadata") or {}).get("policy_override", False)
    policy_result = "FAIL" if (policy_override or category == "sensitive") else "PASS"
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
    return state.transition(policy_result=policy_result, audit_trail=new_trail)


async def score_risk_compliance(
    state: ComplianceState,
    *,
    audit_logger: AuditLogger,
) -> ComplianceState:
    """Deterministic risk scoring for compliance workflow."""
    start = time.perf_counter()
    raw = state.raw_event or {}
    event_type = raw.get("event_type", "standard")
    metadata = raw.get("metadata") or {}
    if event_type == "high_risk":
        risk_score = 85.0
    elif metadata.get("category") == "sensitive":
        risk_score = 70.0
    elif event_type == "low_risk":
        risk_score = 15.0
    else:
        risk_score = 30.0
    elapsed_ms = (time.perf_counter() - start) * 1000
    trail_entry = {
        "node": "risk_scoring",
        "action": "risk_scored",
        "at": datetime.now(timezone.utc).isoformat(),
        "model_version": state.model_version,
        "prompt_version": state.prompt_version,
        "execution_ms": round(elapsed_ms, 2),
        "risk_score": risk_score,
    }
    new_trail = list(state.audit_trail) + [trail_entry]
    await audit_logger.log_action(
        actor=WORKFLOW_ACTOR,
        tenant_id=state.tenant_id,
        action="risk_scored",
        resource_type="workflow",
        resource_id=state.event_id,
        reason="deterministic_scoring",
        correlation_id=state.correlation_id,
        metadata={
            "model_version": state.model_version,
            "prompt_version": state.prompt_version,
            "execution_ms": round(elapsed_ms, 2),
            "risk_score": risk_score,
        },
    )
    return state.transition(risk_score=risk_score, audit_trail=new_trail)


async def apply_guardrails_compliance(
    state: ComplianceState,
    *,
    audit_logger: AuditLogger,
) -> ComplianceState:
    """Guardrails for compliance workflow."""
    start = time.perf_counter()
    raw = state.raw_event or {}
    risk_score = state.risk_score or 0.0
    metadata = raw.get("metadata") or {}
    blocked = metadata.get("blocked_pattern", False)
    over_threshold = risk_score >= HIGH_RISK_THRESHOLD
    guardrail_result = "VIOLATION" if (blocked or over_threshold) else "OK"
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
    return state.transition(guardrail_result=guardrail_result, audit_trail=new_trail)


async def make_compliance_decision(
    state: ComplianceState,
    *,
    audit_logger: AuditLogger,
) -> ComplianceState:
    """
    Compliance decision: automatic approval if low regulatory flags; else escalate (REQUIRE_APPROVAL).
    Also REQUIRE_APPROVAL if policy fail, high risk, or guardrail violation.
    """
    start = time.perf_counter()
    policy_fail = state.policy_result == "FAIL"
    high_risk = (state.risk_score or 0.0) >= HIGH_RISK_THRESHOLD
    guardrail_violation = state.guardrail_result == "VIOLATION"
    has_regulatory_flags = len(state.regulatory_flags or []) > 0
    if policy_fail or high_risk or guardrail_violation or has_regulatory_flags:
        final_decision = "REQUIRE_APPROVAL"
        approval_required = True
    else:
        final_decision = "APPROVED"
        approval_required = False
    elapsed_ms = (time.perf_counter() - start) * 1000
    trail_entry = {
        "node": "decision",
        "action": "decision_made",
        "at": datetime.now(timezone.utc).isoformat(),
        "model_version": state.model_version,
        "prompt_version": state.prompt_version,
        "execution_ms": round(elapsed_ms, 2),
        "final_decision": final_decision,
        "approval_required": approval_required,
    }
    new_trail = list(state.audit_trail) + [trail_entry]
    await audit_logger.log_action(
        actor=WORKFLOW_ACTOR,
        tenant_id=state.tenant_id,
        action="decision_made",
        resource_type="workflow",
        resource_id=state.event_id,
        reason="compliance_decision",
        correlation_id=state.correlation_id,
        metadata={
            "model_version": state.model_version,
            "prompt_version": state.prompt_version,
            "execution_ms": round(elapsed_ms, 2),
            "final_decision": final_decision,
            "approval_required": approval_required,
        },
    )
    logger.info(
        "compliance_decision_node_completed",
        extra={
            "event_id": state.event_id,
            "final_decision": final_decision,
            "approval_required": approval_required,
        },
    )
    return state.transition(
        final_decision=final_decision,
        approval_required=approval_required,
        audit_trail=new_trail,
    )
