"""Compliance workflow: retrieval → policy → scoring → guardrails → compliance decision."""

import logging
import time
from typing import TYPE_CHECKING, Optional

from app.governance.audit_logger import AuditLogger
from app.governance.exceptions import (
    ModelNotApprovedError,
    PromptNotApprovedError,
)
from app.governance.model_registry import ModelRegistry
from app.governance.prompt_registry import PromptRegistry
from app.workflows.langgraph.nodes.compliance_nodes import (
    apply_guardrails_compliance,
    make_compliance_decision,
    retrieve_context_compliance,
    score_risk_compliance,
    validate_policy_compliance,
)
from app.workflows.langgraph.state_models import ComplianceState
from app.workflows.langgraph.workflow_state_store import ComplianceStateStore

if TYPE_CHECKING:
    from app.observability.cost_tracker import CostTracker
    from app.observability.evaluation import EvaluationService
    from app.observability.failure_classifier import FailureClassifier
    from app.observability.langfuse_client import LangfuseClient
    from app.observability.metrics import MetricsCollector
    from app.observability.tracing import TracingService

logger = logging.getLogger(__name__)

DEFAULT_MODEL_VERSION = "simulated@1"
DEFAULT_PROMPT_VERSION = 1
NODE_ORDER = [
    "retrieval",
    "policy_validation",
    "risk_scoring",
    "guardrails",
    "decision",
]


def _node_done_compliance(state: ComplianceState, node: str) -> bool:
    return any((e.get("node") == node for e in state.audit_trail))


class ComplianceWorkflow:
    """
    Compliance workflow with additional compliance gating.
    Automatic approval if low regulatory flags; escalate otherwise.
    Idempotent when state_store is provided. Optional observability hooks.
    """

    def __init__(
        self,
        audit_logger: AuditLogger,
        state_store: Optional[ComplianceStateStore] = None,
        model_registry: Optional[ModelRegistry] = None,
        prompt_registry: Optional[PromptRegistry] = None,
        metrics_collector: Optional["MetricsCollector"] = None,
        tracing_service: Optional["TracingService"] = None,
        cost_tracker: Optional["CostTracker"] = None,
        failure_classifier: Optional["FailureClassifier"] = None,
        langfuse_client: Optional["LangfuseClient"] = None,
        evaluation_service: Optional["EvaluationService"] = None,
    ) -> None:
        self._audit = audit_logger
        self._store = state_store
        self._model_registry = model_registry
        self._prompt_registry = prompt_registry
        self._metrics = metrics_collector
        self._tracing = tracing_service
        self._cost = cost_tracker
        self._failure_classifier = failure_classifier
        self._langfuse = langfuse_client
        self._evaluation = evaluation_service

    async def _resolve_versions(self, state: ComplianceState) -> ComplianceState:
        """Set model_version and prompt_version from registries. Enforces model and prompt approval."""
        model_version = DEFAULT_MODEL_VERSION
        prompt_version = DEFAULT_PROMPT_VERSION
        if self._model_registry:
            record = await self._model_registry.get_approved_model("compliance-model")
            model_version = f"{record.model_name}@{record.version}"
        if self._prompt_registry:
            prompt_record = await self._prompt_registry.get_approved_prompt(
                "compliance-prompt"
            )
            prompt_version = prompt_record.version
        if (
            state.model_version != model_version
            or state.prompt_version != prompt_version
        ):
            return state.transition(
                model_version=model_version, prompt_version=prompt_version
            )
        return state

    async def run(self, state: ComplianceState) -> ComplianceState:
        """Run compliance workflow. Return cached state if idempotent hit. Observability when enabled."""
        if self._metrics:
            self._metrics.increment("request_count", 1, tenant_id=state.tenant_id)
            self._metrics.increment("workflow_execution_count")

        request_start = time.perf_counter()
        trace_id: Optional[str] = None
        parent_span_id: Optional[str] = None
        current: ComplianceState = state

        async def run_node(name: str, run_fn):
            nonlocal current
            node_start = time.perf_counter()
            if self._tracing and trace_id:
                async with self._tracing.start_span(
                    name,
                    trace_id=trace_id,
                    parent_span_id=parent_span_id,
                    tenant_id=current.tenant_id,
                    correlation_id=current.correlation_id,
                    model_version=current.model_version,
                    prompt_version=current.prompt_version,
                ):
                    out = await run_fn()
            else:
                out = await run_fn()
            elapsed_ms = (time.perf_counter() - node_start) * 1000
            if self._metrics:
                self._metrics.observe_latency(
                    "node_execution_latency", elapsed_ms, node=name
                )
                self._metrics.increment("model_usage_count")
                self._metrics.increment("prompt_usage_count")
            return out

        async def run_all_nodes() -> ComplianceState:
            nonlocal current
            if not _node_done_compliance(current, "retrieval"):
                current = await run_node(
                    "retrieval",
                    lambda: retrieve_context_compliance(
                        current, audit_logger=self._audit
                    ),
                )
            if not _node_done_compliance(current, "policy_validation"):
                current = await run_node(
                    "policy_validation",
                    lambda: validate_policy_compliance(
                        current, audit_logger=self._audit
                    ),
                )
            if not _node_done_compliance(current, "risk_scoring"):
                current = await run_node(
                    "risk_scoring",
                    lambda: score_risk_compliance(current, audit_logger=self._audit),
                )
            if not _node_done_compliance(current, "guardrails"):
                current = await run_node(
                    "guardrails",
                    lambda: apply_guardrails_compliance(
                        current, audit_logger=self._audit
                    ),
                )
            if not _node_done_compliance(current, "decision"):
                current = await run_node(
                    "decision",
                    lambda: make_compliance_decision(current, audit_logger=self._audit),
                )
            return current

        try:
            if self._store:
                cached = await self._store.get_compliance_state(state.event_id)
                if cached is not None:
                    logger.info(
                        "compliance_workflow_idempotent_skip",
                        extra={
                            "event_id": state.event_id,
                            "correlation_id": state.correlation_id,
                        },
                    )
                    return cached

            try:
                current = await self._resolve_versions(state)
            except (ModelNotApprovedError, PromptNotApprovedError) as gov_err:
                resource_type = (
                    "model" if isinstance(gov_err, ModelNotApprovedError) else "prompt"
                )
                resource_id = (
                    "compliance-model"
                    if isinstance(gov_err, ModelNotApprovedError)
                    else "compliance-prompt"
                )
                await self._audit.log_action(
                    actor="system",
                    tenant_id=state.tenant_id,
                    action="GOVERNANCE_VIOLATION",
                    resource_type=resource_type,
                    resource_id=resource_id,
                    reason=gov_err.message,
                    correlation_id=state.correlation_id,
                    metadata={
                        "exception_type": type(gov_err).__name__,
                        "event_id": state.event_id,
                    },
                )
                raise

            if self._tracing:
                async with self._tracing.start_span(
                    "compliance_workflow",
                    tenant_id=state.tenant_id,
                    correlation_id=state.correlation_id,
                ) as root_span:
                    trace_id = root_span.trace_id
                    parent_span_id = root_span.span_id
                    current = await run_all_nodes()
            else:
                current = await run_all_nodes()

            if self._metrics and (
                current.approval_required
                or current.final_decision == "REQUIRE_APPROVAL"
            ):
                self._metrics.increment("approval_required_count")

            request_latency_ms = (time.perf_counter() - request_start) * 1000
            if self._metrics:
                self._metrics.observe_latency("request_latency", request_latency_ms)

            if self._cost:
                self._cost.add_cost(
                    current.tenant_id,
                    0.01,
                    model_version=current.model_version,
                    request_id=current.event_id,
                )

            if self._langfuse:
                await self._langfuse.log_generation(
                    event_id=current.event_id,
                    tenant_id=current.tenant_id,
                    prompt_version=current.prompt_version,
                    model_version=current.model_version,
                    input_tokens=100,
                    output_tokens=50,
                    latency_ms=request_latency_ms,
                )

            if self._evaluation:
                eval_result = await self._evaluation.evaluate_decision(
                    tenant_id=current.tenant_id,
                    event_id=current.event_id,
                    correlation_id=current.correlation_id,
                    final_decision=current.final_decision or "",
                    policy_result=current.policy_result or "",
                    guardrail_result=current.guardrail_result or "",
                    risk_score=current.risk_score,
                )
                current = current.transition(evaluation_result=eval_result.to_dict())

            if self._store:
                await self._store.set_compliance_state(current.event_id, current)

            return current

        except Exception as e:
            if self._failure_classifier and self._metrics:
                cat = self._failure_classifier.classify(e)
                self._metrics.increment("failure_count", 1, category=cat.value)
            raise
