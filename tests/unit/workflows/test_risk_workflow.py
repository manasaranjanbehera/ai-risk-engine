"""Risk workflow tests: happy path, policy fail, high risk, idempotency, audit trail."""

from unittest.mock import AsyncMock

import pytest

from app.governance.exceptions import ModelNotApprovedError
from app.governance.model_registry import ModelRegistry, ModelRecord
from app.workflows.langgraph.risk_workflow import RiskWorkflow
from app.workflows.langgraph.state_models import RiskState


@pytest.mark.asyncio
async def test_risk_workflow_full_happy_path(audit_logger):
    """Full run: retrieval -> policy -> scoring -> guardrails -> decision -> APPROVED."""
    workflow = RiskWorkflow(audit_logger=audit_logger, state_store=None)
    state = RiskState(
        event_id="e1",
        tenant_id="t1",
        correlation_id="c1",
        raw_event={"event_type": "standard", "metadata": {"category": "normal"}},
        audit_trail=[],
    )
    out = await workflow.run(state)
    assert out.final_decision == "APPROVED"
    assert out.retrieved_context is not None
    assert out.policy_result == "PASS"
    assert out.risk_score == 30.0
    assert out.guardrail_result == "OK"


@pytest.mark.asyncio
async def test_risk_workflow_policy_fail_triggers_approval(audit_logger):
    """Policy FAIL must lead to REQUIRE_APPROVAL."""
    workflow = RiskWorkflow(audit_logger=audit_logger, state_store=None)
    state = RiskState(
        event_id="e2",
        tenant_id="t1",
        correlation_id="c2",
        raw_event={"event_type": "standard", "metadata": {"category": "sensitive"}},
        audit_trail=[],
    )
    out = await workflow.run(state)
    assert out.policy_result == "FAIL"
    assert out.final_decision == "REQUIRE_APPROVAL"


@pytest.mark.asyncio
async def test_risk_workflow_high_risk_triggers_approval(audit_logger):
    """High risk score must lead to REQUIRE_APPROVAL."""
    workflow = RiskWorkflow(audit_logger=audit_logger, state_store=None)
    state = RiskState(
        event_id="e3",
        tenant_id="t1",
        correlation_id="c3",
        raw_event={"event_type": "high_risk"},
        audit_trail=[],
    )
    out = await workflow.run(state)
    assert out.risk_score == 85.0
    assert out.final_decision == "REQUIRE_APPROVAL"


@pytest.mark.asyncio
async def test_risk_workflow_idempotency_skip(audit_logger):
    """If state_store returns cached state, workflow must return it without re-running nodes."""
    cached_state = RiskState(
        event_id="e4",
        tenant_id="t1",
        correlation_id="c4",
        final_decision="APPROVED",
        risk_score=20.0,
        audit_trail=[{"node": "decision", "action": "decision_made"}],
    )
    store = AsyncMock()
    store.get_risk_state = AsyncMock(return_value=cached_state)
    store.set_risk_state = AsyncMock(return_value=None)
    workflow = RiskWorkflow(audit_logger=audit_logger, state_store=store)
    state = RiskState(
        event_id="e4",
        tenant_id="t1",
        correlation_id="c4",
        raw_event={},
        audit_trail=[],
    )
    out = await workflow.run(state)
    assert out.final_decision == "APPROVED"
    assert out.risk_score == 20.0
    store.get_risk_state.assert_awaited_once_with("e4")
    store.set_risk_state.assert_not_awaited()


@pytest.mark.asyncio
async def test_risk_workflow_audit_trail_length(audit_logger):
    """After full run, audit_trail must have one entry per node (5 nodes)."""
    workflow = RiskWorkflow(audit_logger=audit_logger, state_store=None)
    state = RiskState(
        event_id="e5",
        tenant_id="t1",
        correlation_id="c5",
        raw_event={"event_type": "standard"},
        audit_trail=[],
    )
    out = await workflow.run(state)
    nodes_in_trail = [e["node"] for e in out.audit_trail]
    assert "retrieval" in nodes_in_trail
    assert "policy_validation" in nodes_in_trail
    assert "risk_scoring" in nodes_in_trail
    assert "guardrails" in nodes_in_trail
    assert "decision" in nodes_in_trail
    assert len(out.audit_trail) == 5


@pytest.mark.asyncio
async def test_risk_workflow_stores_result_when_store_provided(audit_logger):
    """When state_store is provided, final state must be stored after run."""
    store = AsyncMock()
    store.get_risk_state = AsyncMock(return_value=None)
    store.set_risk_state = AsyncMock(return_value=None)
    workflow = RiskWorkflow(audit_logger=audit_logger, state_store=store)
    state = RiskState(
        event_id="e6",
        tenant_id="t1",
        correlation_id="c6",
        raw_event={"event_type": "standard"},
        audit_trail=[],
    )
    out = await workflow.run(state)
    store.set_risk_state.assert_awaited_once()
    call_args = store.set_risk_state.call_args
    assert call_args[0][0] == "e6"
    assert call_args[0][1].event_id == "e6"
    assert call_args[0][1].final_decision == out.final_decision


@pytest.mark.asyncio
async def test_risk_workflow_fails_when_model_registered_but_not_approved(audit_logger):
    """When model_registry is provided and model is registered but not approved, run raises ModelNotApprovedError."""
    store: dict[tuple[str, str], ModelRecord] = {}
    latest: dict[str, ModelRecord] = {}

    async def save(r: ModelRecord) -> None:
        store[(r.model_name, r.version)] = r
        latest[r.model_name] = r

    async def get(name: str, version: str):
        return store.get((name, version))

    async def get_latest(name: str):
        return latest.get(name)

    repo = AsyncMock()
    repo.save = save
    repo.get = get
    repo.get_latest = get_latest

    audit = AsyncMock()
    audit.log_action = AsyncMock(return_value=None)

    registry = ModelRegistry(repository=repo, audit_logger=audit)
    await registry.register_model(
        model_name="risk-model",
        version="1.0",
        checksum="abc",
        correlation_id="c1",
        tenant_id="t1",
    )
    workflow = RiskWorkflow(
        audit_logger=audit_logger,
        state_store=None,
        model_registry=registry,
    )
    state = RiskState(
        event_id="e7",
        tenant_id="t1",
        correlation_id="c7",
        raw_event={"event_type": "standard"},
        audit_trail=[],
    )
    with pytest.raises(ModelNotApprovedError) as exc_info:
        await workflow.run(state)
    assert "unapproved" in str(exc_info.value.message).lower() or "risk-model" in str(
        exc_info.value.message
    )


@pytest.mark.asyncio
async def test_risk_workflow_model_not_approved_emits_governance_violation_audit(
    audit_logger,
):
    """When model is not approved, workflow logs GOVERNANCE_VIOLATION before raising."""
    from app.governance.model_registry import ModelRegistry, ModelRecord

    store = {}
    latest = {}

    async def save(r: ModelRecord) -> None:
        store[(r.model_name, r.version)] = r
        latest[r.model_name] = r

    async def get(name: str, version: str):
        return store.get((name, version))

    async def get_latest(name: str):
        return latest.get(name)

    repo = AsyncMock()
    repo.save = save
    repo.get = get
    repo.get_latest = get_latest
    registry_audit = AsyncMock()
    registry_audit.log_action = AsyncMock(return_value=None)
    registry = ModelRegistry(repository=repo, audit_logger=registry_audit)
    await registry.register_model(
        model_name="risk-model",
        version="1.0",
        checksum="x",
        correlation_id="c1",
        tenant_id="t1",
    )
    workflow_audit = AsyncMock()
    workflow_audit.log_action = AsyncMock(return_value=None)
    workflow = RiskWorkflow(
        audit_logger=workflow_audit,
        state_store=None,
        model_registry=registry,
    )
    state = RiskState(
        event_id="e7b",
        tenant_id="t1",
        correlation_id="c7b",
        raw_event={"event_type": "standard"},
        audit_trail=[],
    )
    with pytest.raises(ModelNotApprovedError):
        await workflow.run(state)
    workflow_audit.log_action.assert_awaited_once()
    call_kw = workflow_audit.log_action.call_args[1]
    assert call_kw["action"] == "GOVERNANCE_VIOLATION"
    assert call_kw["tenant_id"] == "t1"
    assert call_kw["correlation_id"] == "c7b"
    assert call_kw["resource_type"] == "model"
    assert call_kw["resource_id"] == "risk-model"
    assert "unapproved" in (call_kw.get("reason") or "").lower() or "risk-model" in (
        call_kw.get("reason") or ""
    )


@pytest.mark.asyncio
async def test_risk_workflow_prompt_not_approved_blocks_execution(audit_logger):
    """When prompt_registry is provided and prompt is not found, run raises PromptNotApprovedError."""
    from app.governance.exceptions import PromptNotApprovedError
    from app.governance.prompt_registry import PromptRegistry

    prompt_repo = AsyncMock()
    prompt_repo.get = AsyncMock(return_value=None)
    prompt_repo.get_versions = AsyncMock(return_value=[])
    prompt_audit = AsyncMock()
    prompt_audit.log_action = AsyncMock(return_value=None)
    prompt_registry = PromptRegistry(
        repository=prompt_repo,
        audit_logger=prompt_audit,
    )
    workflow = RiskWorkflow(
        audit_logger=audit_logger,
        state_store=None,
        prompt_registry=prompt_registry,
    )
    state = RiskState(
        event_id="e8",
        tenant_id="t1",
        correlation_id="c8",
        raw_event={"event_type": "standard"},
        audit_trail=[],
    )
    with pytest.raises(PromptNotApprovedError) as exc_info:
        await workflow.run(state)
    assert (
        "risk-prompt" in str(exc_info.value.message)
        or "not approved" in str(exc_info.value.message).lower()
    )


@pytest.mark.asyncio
async def test_risk_workflow_prompt_not_approved_emits_governance_violation_audit(
    audit_logger,
):
    """When prompt is not approved, workflow logs GOVERNANCE_VIOLATION before raising."""
    from app.governance.exceptions import PromptNotApprovedError
    from app.governance.prompt_registry import PromptRegistry

    prompt_repo = AsyncMock()
    prompt_repo.get = AsyncMock(return_value=None)
    prompt_repo.get_versions = AsyncMock(return_value=[])
    prompt_audit = AsyncMock()
    prompt_audit.log_action = AsyncMock(return_value=None)
    prompt_registry = PromptRegistry(
        repository=prompt_repo,
        audit_logger=prompt_audit,
    )
    workflow_audit = AsyncMock()
    workflow_audit.log_action = AsyncMock(return_value=None)
    workflow = RiskWorkflow(
        audit_logger=workflow_audit,
        state_store=None,
        prompt_registry=prompt_registry,
    )
    state = RiskState(
        event_id="e8b",
        tenant_id="t1",
        correlation_id="c8b",
        raw_event={"event_type": "standard"},
        audit_trail=[],
    )
    with pytest.raises(PromptNotApprovedError):
        await workflow.run(state)
    workflow_audit.log_action.assert_awaited_once()
    call_kw = workflow_audit.log_action.call_args[1]
    assert call_kw["action"] == "GOVERNANCE_VIOLATION"
    assert call_kw["tenant_id"] == "t1"
    assert call_kw["correlation_id"] == "c8b"
    assert call_kw["resource_type"] == "prompt"
    assert call_kw["resource_id"] == "risk-prompt"
