"""Compliance workflow tests: regulatory flag escalation, low risk auto-approval, deterministic."""

from unittest.mock import AsyncMock

import pytest

from app.governance.exceptions import ModelNotApprovedError, PromptNotApprovedError
from app.governance.model_registry import ModelRegistry, ModelRecord
from app.governance.prompt_registry import PromptRegistry
from app.workflows.langgraph.compliance_workflow import ComplianceWorkflow
from app.workflows.langgraph.state_models import ComplianceState


@pytest.mark.asyncio
async def test_compliance_regulatory_flag_triggers_escalation(audit_logger):
    """Presence of regulatory_flags must lead to REQUIRE_APPROVAL and approval_required=True."""
    workflow = ComplianceWorkflow(audit_logger=audit_logger, state_store=None)
    state = ComplianceState(
        event_id="e1",
        tenant_id="t1",
        correlation_id="c1",
        raw_event={"event_type": "low_risk"},
        regulatory_flags=["GDPR"],
        audit_trail=[],
    )
    out = await workflow.run(state)
    assert out.final_decision == "REQUIRE_APPROVAL"
    assert out.approval_required is True


@pytest.mark.asyncio
async def test_compliance_low_risk_auto_approval(audit_logger):
    """Low risk, no flags, policy pass -> APPROVED, approval_required=False."""
    workflow = ComplianceWorkflow(audit_logger=audit_logger, state_store=None)
    state = ComplianceState(
        event_id="e2",
        tenant_id="t1",
        correlation_id="c2",
        raw_event={"event_type": "low_risk", "metadata": {"category": "normal"}},
        regulatory_flags=[],
        audit_trail=[],
    )
    out = await workflow.run(state)
    assert out.final_decision == "APPROVED"
    assert out.approval_required is False
    assert out.risk_score == 15.0


@pytest.mark.asyncio
async def test_compliance_deterministic_decision(audit_logger):
    """Same input must produce same decision (no randomness)."""
    workflow = ComplianceWorkflow(audit_logger=audit_logger, state_store=None)
    state = ComplianceState(
        event_id="e3",
        tenant_id="t1",
        correlation_id="c3",
        raw_event={"event_type": "standard"},
        regulatory_flags=[],
        audit_trail=[],
    )
    out1 = await workflow.run(state)
    state2 = ComplianceState(
        event_id="e3b",
        tenant_id="t1",
        correlation_id="c3b",
        raw_event={"event_type": "standard"},
        regulatory_flags=[],
        audit_trail=[],
    )
    out2 = await workflow.run(state2)
    assert out1.final_decision == out2.final_decision
    assert out1.risk_score == out2.risk_score


@pytest.mark.asyncio
async def test_compliance_idempotency_skip(audit_logger):
    """Cached compliance state must be returned without re-running."""
    cached = ComplianceState(
        event_id="e4",
        tenant_id="t1",
        correlation_id="c4",
        final_decision="APPROVED",
        approval_required=False,
        audit_trail=[{"node": "decision"}],
    )
    store = AsyncMock()
    store.get_compliance_state = AsyncMock(return_value=cached)
    store.set_compliance_state = AsyncMock(return_value=None)
    workflow = ComplianceWorkflow(audit_logger=audit_logger, state_store=store)
    state = ComplianceState(
        event_id="e4",
        tenant_id="t1",
        correlation_id="c4",
        raw_event={},
        audit_trail=[],
    )
    out = await workflow.run(state)
    assert out.final_decision == "APPROVED"
    store.get_compliance_state.assert_awaited_once_with("e4")
    store.set_compliance_state.assert_not_awaited()


@pytest.mark.asyncio
async def test_compliance_workflow_model_not_approved_blocks_execution(audit_logger):
    """When model_registry is provided and model is not approved, run raises ModelNotApprovedError."""
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
    reg_audit = AsyncMock()
    reg_audit.log_action = AsyncMock(return_value=None)
    registry = ModelRegistry(repository=repo, audit_logger=reg_audit)
    await registry.register_model(
        model_name="compliance-model",
        version="1.0",
        checksum="x",
        correlation_id="c1",
        tenant_id="t1",
    )
    workflow = ComplianceWorkflow(
        audit_logger=audit_logger,
        state_store=None,
        model_registry=registry,
    )
    state = ComplianceState(
        event_id="e5",
        tenant_id="t1",
        correlation_id="c5",
        raw_event={"event_type": "standard"},
        regulatory_flags=[],
        audit_trail=[],
    )
    with pytest.raises(ModelNotApprovedError):
        await workflow.run(state)


@pytest.mark.asyncio
async def test_compliance_workflow_prompt_not_approved_blocks_execution(audit_logger):
    """When prompt_registry is provided and prompt is not found, run raises PromptNotApprovedError."""
    prompt_repo = AsyncMock()
    prompt_repo.get = AsyncMock(return_value=None)
    prompt_repo.get_versions = AsyncMock(return_value=[])
    prompt_audit = AsyncMock()
    prompt_audit.log_action = AsyncMock(return_value=None)
    prompt_registry = PromptRegistry(
        repository=prompt_repo,
        audit_logger=prompt_audit,
    )
    workflow = ComplianceWorkflow(
        audit_logger=audit_logger,
        state_store=None,
        prompt_registry=prompt_registry,
    )
    state = ComplianceState(
        event_id="e6",
        tenant_id="t1",
        correlation_id="c6",
        raw_event={"event_type": "standard"},
        regulatory_flags=[],
        audit_trail=[],
    )
    with pytest.raises(PromptNotApprovedError):
        await workflow.run(state)


@pytest.mark.asyncio
async def test_compliance_workflow_governance_violation_audit_emitted(audit_logger):
    """When model is not approved, compliance workflow logs GOVERNANCE_VIOLATION before raising."""
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
    reg_audit = AsyncMock()
    reg_audit.log_action = AsyncMock(return_value=None)
    registry = ModelRegistry(repository=repo, audit_logger=reg_audit)
    await registry.register_model(
        model_name="compliance-model",
        version="1.0",
        checksum="x",
        correlation_id="c1",
        tenant_id="t1",
    )
    workflow_audit = AsyncMock()
    workflow_audit.log_action = AsyncMock(return_value=None)
    workflow = ComplianceWorkflow(
        audit_logger=workflow_audit,
        state_store=None,
        model_registry=registry,
    )
    state = ComplianceState(
        event_id="e7",
        tenant_id="t1",
        correlation_id="c7",
        raw_event={"event_type": "standard"},
        regulatory_flags=[],
        audit_trail=[],
    )
    with pytest.raises(ModelNotApprovedError):
        await workflow.run(state)
    workflow_audit.log_action.assert_awaited_once()
    call_kw = workflow_audit.log_action.call_args[1]
    assert call_kw["action"] == "GOVERNANCE_VIOLATION"
    assert call_kw["tenant_id"] == "t1"
    assert call_kw["correlation_id"] == "c7"
    assert call_kw["resource_id"] == "compliance-model"
