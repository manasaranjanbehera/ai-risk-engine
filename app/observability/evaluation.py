"""Quality scoring for decisions. Deterministic scores, audit emission."""

from typing import Any

from app.governance.audit_logger import AuditLogger


class EvaluationResult:
    """Result of evaluate_decision."""

    def __init__(
        self,
        confidence_score: float,
        policy_alignment_score: float,
        guardrail_score: float,
        overall_quality_score: float,
    ) -> None:
        self.confidence_score = confidence_score
        self.policy_alignment_score = policy_alignment_score
        self.guardrail_score = guardrail_score
        self.overall_quality_score = overall_quality_score

    def to_dict(self) -> dict[str, Any]:
        return {
            "confidence_score": self.confidence_score,
            "policy_alignment_score": self.policy_alignment_score,
            "guardrail_score": self.guardrail_score,
            "overall_quality_score": self.overall_quality_score,
        }


class EvaluationService:
    """
    Evaluates decision quality: confidence, policy alignment, guardrail, overall.
    Deterministic. Stores result in workflow state (caller attaches); emits audit event.
    """

    def __init__(self, audit_logger: AuditLogger | None = None) -> None:
        self._audit = audit_logger

    async def evaluate_decision(
        self,
        *,
        tenant_id: str,
        event_id: str,
        correlation_id: str,
        final_decision: str,
        policy_result: str,
        guardrail_result: str,
        risk_score: float | None,
    ) -> EvaluationResult:
        """
        Compute deterministic quality scores. All scores in [0.0, 1.0].
        Emit audit event with evaluation result.
        """
        # Deterministic: derive from inputs
        policy_ok = 1.0 if policy_result == "PASS" else 0.0
        guardrail_ok = 1.0 if guardrail_result == "OK" else 0.0
        risk_normalized = 1.0 - ((risk_score or 0) / 100.0)
        confidence = (policy_ok + guardrail_ok + risk_normalized) / 3.0
        policy_alignment = policy_ok
        guardrail_score = guardrail_ok
        overall = (confidence + policy_alignment + guardrail_score) / 3.0

        result = EvaluationResult(
            confidence_score=round(confidence, 4),
            policy_alignment_score=round(policy_alignment, 4),
            guardrail_score=round(guardrail_score, 4),
            overall_quality_score=round(overall, 4),
        )

        if self._audit:
            await self._audit.log_action(
                actor="evaluation_service",
                tenant_id=tenant_id,
                action="evaluation_completed",
                resource_type="workflow",
                resource_id=event_id,
                reason="quality_scoring",
                correlation_id=correlation_id,
                metadata={"evaluation": result.to_dict()},
            )

        return result
