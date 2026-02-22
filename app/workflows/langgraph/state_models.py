"""Deterministic state containers for AI workflows. Immutable transitions, fully serializable."""

from typing import Any

from pydantic import BaseModel, Field


class RiskState(BaseModel):
    """
    State for the risk workflow. All transitions return new state; no in-place mutation.
    Fully serializable for idempotency cache and audit.
    """

    event_id: str
    tenant_id: str
    correlation_id: str
    raw_event: dict[str, Any] = Field(default_factory=dict)
    retrieved_context: str | None = None
    policy_result: str | None = None  # "PASS" | "FAIL"
    risk_score: float | None = None
    guardrail_result: str | None = None  # e.g. "OK" | "VIOLATION"
    final_decision: str | None = None  # "APPROVED" | "REQUIRE_APPROVAL"
    model_version: str = "simulated@1"
    prompt_version: int = 1
    audit_trail: list[dict[str, Any]] = Field(default_factory=list)
    idempotency_key: str | None = None
    evaluation_result: dict[str, Any] | None = None

    model_config = {
        "frozen": False
    }  # Pydantic allows copy; we never mutate in place in nodes

    def transition(self, **updates: Any) -> "RiskState":
        """Return a new state with the given updates. Original unchanged."""
        return self.model_copy(update=updates, deep=True)


class ComplianceState(BaseModel):
    """
    State for the compliance workflow. Similar to RiskState with compliance-specific fields.
    Immutable transitions; fully serializable.
    """

    event_id: str
    tenant_id: str
    correlation_id: str
    raw_event: dict[str, Any] = Field(default_factory=dict)
    retrieved_context: str | None = None
    policy_result: str | None = None
    risk_score: float | None = None
    guardrail_result: str | None = None
    regulatory_flags: list[str] = Field(default_factory=list)
    approval_required: bool = False
    final_decision: str | None = None
    model_version: str = "simulated@1"
    prompt_version: int = 1
    audit_trail: list[dict[str, Any]] = Field(default_factory=list)
    idempotency_key: str | None = None
    evaluation_result: dict[str, Any] | None = None

    model_config = {"frozen": False}

    def transition(self, **updates: Any) -> "ComplianceState":
        """Return a new state with the given updates. Original unchanged."""
        return self.model_copy(update=updates, deep=True)
