"""Governance tests: prompt version increments correctly; immutable previous versions."""

from unittest.mock import AsyncMock

import pytest

from app.governance.exceptions import PromptNotApprovedError
from app.governance.prompt_registry import PromptRegistry, PromptRecord


@pytest.fixture
def prompt_repo():
    store: list[PromptRecord] = []

    async def save(r: PromptRecord) -> None:
        store.append(r)

    async def get(pid: str, version: int | None = None):
        matches = [x for x in store if x.prompt_id == pid]
        if not matches:
            return None
        if version is not None:
            for x in matches:
                if x.version == version:
                    return x
            return None
        return max(matches, key=lambda x: x.version)

    async def get_versions(pid: str):
        matches = [x for x in store if x.prompt_id == pid]
        return sorted(matches, key=lambda x: x.version, reverse=True)

    repo = AsyncMock()
    repo.save = save
    repo.get = get
    repo.get_versions = get_versions
    return repo


@pytest.fixture
def audit_logger():
    a = AsyncMock()
    a.log_action = AsyncMock(return_value=None)
    return a


@pytest.fixture
def prompt_registry(prompt_repo, audit_logger):
    return PromptRegistry(repository=prompt_repo, audit_logger=audit_logger)


async def test_prompt_version_increments_correctly(prompt_registry, prompt_repo):
    await prompt_registry.register_prompt(
        prompt_id="p1",
        name="Prompt 1",
        content="Hello",
        change_reason="initial",
        author="alice",
        tenant_id="t1",
        correlation_id="c1",
    )
    r1 = await prompt_registry.get_prompt("p1", None)
    assert r1 is not None
    assert r1.version == 1

    await prompt_registry.update_prompt(
        prompt_id="p1",
        content="Hello v2",
        change_reason="update",
        author="bob",
        tenant_id="t1",
        correlation_id="c2",
    )
    r2 = await prompt_registry.get_prompt("p1", None)
    assert r2 is not None
    assert r2.version == 2
    assert r2.content == "Hello v2"

    r1_again = await prompt_registry.get_prompt("p1", 1)
    assert r1_again is not None
    assert r1_again.version == 1
    assert r1_again.content == "Hello"


async def test_prompt_audit_every_change(prompt_registry, audit_logger):
    await prompt_registry.register_prompt(
        prompt_id="p1",
        name="P",
        content="c",
        change_reason="r",
        author="a",
        tenant_id="t1",
        correlation_id="c1",
    )
    assert audit_logger.log_action.await_count == 1
    await prompt_registry.update_prompt(
        prompt_id="p1",
        content="c2",
        change_reason="r2",
        author="a",
        tenant_id="t1",
        correlation_id="c2",
    )
    assert audit_logger.log_action.await_count == 2


async def test_get_approved_prompt_raises_when_not_found(prompt_registry):
    """get_approved_prompt raises PromptNotApprovedError when prompt does not exist."""
    with pytest.raises(PromptNotApprovedError) as exc_info:
        await prompt_registry.get_approved_prompt("nonexistent")
    assert "nonexistent" in str(exc_info.value.message)


async def test_get_approved_prompt_returns_record_when_found(prompt_registry):
    """get_approved_prompt returns the prompt record when it exists."""
    await prompt_registry.register_prompt(
        prompt_id="p1",
        name="Prompt 1",
        content="Hello",
        change_reason="initial",
        author="alice",
        tenant_id="t1",
        correlation_id="c1",
    )
    record = await prompt_registry.get_approved_prompt("p1")
    assert record is not None
    assert record.prompt_id == "p1"
    assert record.version == 1
    assert record.content == "Hello"
