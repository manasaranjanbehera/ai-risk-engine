"""Governance tests: model cannot be approved twice; cannot deploy unapproved model."""

from unittest.mock import AsyncMock

import pytest

from app.governance.exceptions import InvalidModelStateError, ModelNotApprovedError
from app.governance.model_registry import ModelRegistry, ModelRecord, ModelStatus


@pytest.fixture
def model_repo():
    repo = AsyncMock()
    store: dict[tuple[str, str], ModelRecord] = {}
    latest: dict[str, ModelRecord] = {}

    async def save(r: ModelRecord) -> None:
        store[(r.model_name, r.version)] = r
        latest[r.model_name] = r

    async def get(name: str, version: str):
        return store.get((name, version))

    async def get_latest(name: str):
        return latest.get(name)

    repo.save = save
    repo.get = get
    repo.get_latest = get_latest
    return repo


@pytest.fixture
def audit_logger():
    a = AsyncMock()
    a.log_action = AsyncMock(return_value=None)
    return a


@pytest.fixture
def model_registry(model_repo, audit_logger):
    return ModelRegistry(repository=model_repo, audit_logger=audit_logger)


async def test_register_model(model_registry):
    r = await model_registry.register_model(
        model_name="m1",
        version="1.0",
        checksum="abc",
        correlation_id="c1",
        tenant_id="t1",
    )
    assert r.model_name == "m1"
    assert r.version == "1.0"
    assert r.status == ModelStatus.PENDING
    assert r.approved is False


async def test_approve_model_emits_audit(model_registry, audit_logger):
    await model_registry.register_model(
        model_name="m1",
        version="1.0",
        checksum="x",
        correlation_id="c1",
        tenant_id="t1",
    )
    approved = await model_registry.approve_model(
        model_name="m1",
        version="1.0",
        approved_by="admin",
        tenant_id="t1",
        correlation_id="c1",
        reason="ok",
    )
    assert approved.status == ModelStatus.APPROVED
    assert approved.approved_by == "admin"
    audit_logger.log_action.assert_awaited_once()
    call_kw = audit_logger.log_action.call_args[1]
    assert call_kw["action"] == "model_approved"
    assert call_kw["actor"] == "admin"


async def test_model_cannot_be_approved_twice(model_registry):
    await model_registry.register_model(
        model_name="m1",
        version="1.0",
        checksum="x",
        correlation_id="c1",
        tenant_id="t1",
    )
    await model_registry.approve_model(
        model_name="m1",
        version="1.0",
        approved_by="admin",
        tenant_id="t1",
        correlation_id="c1",
    )
    with pytest.raises(InvalidModelStateError) as exc_info:
        await model_registry.approve_model(
            model_name="m1",
            version="1.0",
            approved_by="admin",
            tenant_id="t1",
            correlation_id="c2",
        )
    assert "already approved" in str(exc_info.value.message).lower()


async def test_cannot_deploy_unapproved_model(model_registry):
    await model_registry.register_model(
        model_name="m1",
        version="1.0",
        checksum="x",
        correlation_id="c1",
        tenant_id="t1",
    )
    with pytest.raises(ModelNotApprovedError) as exc_info:
        await model_registry.get_approved_model("m1", "1.0")
    assert (
        "unapproved" in str(exc_info.value.message).lower()
        or "not found" in str(exc_info.value.message).lower()
    )


async def test_get_approved_model_succeeds_when_approved(model_registry):
    await model_registry.register_model(
        model_name="m1",
        version="1.0",
        checksum="x",
        correlation_id="c1",
        tenant_id="t1",
    )
    await model_registry.approve_model(
        model_name="m1",
        version="1.0",
        approved_by="admin",
        tenant_id="t1",
        correlation_id="c1",
    )
    r = await model_registry.get_approved_model("m1", "1.0")
    assert r.is_deployable()
    assert r.status == ModelStatus.APPROVED
