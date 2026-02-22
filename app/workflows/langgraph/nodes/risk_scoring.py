"""Risk scoring node: deterministic score from event type and metadata."""

import logging
import time
from datetime import datetime, timezone

from app.governance.audit_logger import AuditLogger
from app.workflows.langgraph.state_models import RiskState

logger = logging.getLogger(__name__)

WORKFLOW_ACTOR = "workflow"


async def score_risk(
    state: RiskState,
    *,
    audit_logger: AuditLogger,
) -> RiskState:
    """
    Deterministic risk scoring based on event type and metadata.
    Score in [0.0, 100.0]. No randomness.
    """
    start = time.perf_counter()
    raw = state.raw_event or {}
    event_type = raw.get("event_type", "standard")
    metadata = raw.get("metadata") or {}
    # Deterministic mapping: high_risk -> 85, sensitive -> 70, standard -> 30
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
    logger.info(
        "risk_scoring_node_completed",
        extra={
            "event_id": state.event_id,
            "risk_score": risk_score,
            "model_version": state.model_version,
        },
    )
    return state.transition(
        risk_score=risk_score,
        audit_trail=new_trail,
    )
