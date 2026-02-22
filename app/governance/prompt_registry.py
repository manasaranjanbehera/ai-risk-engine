"""Versioned prompt tracking. Immutable previous versions, audit every change. No FastAPI."""

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import List, Optional, Protocol

from app.governance.audit_logger import AuditLogger


@dataclass(frozen=True)
class PromptRecord:
    """Single version of a prompt. Immutable."""

    prompt_id: str
    name: str
    version: int
    content: str
    change_reason: str
    author: str
    created_at: datetime


class PromptRegistryRepository(Protocol):
    """Storage for versioned prompts. Previous versions immutable."""

    async def save(self, record: PromptRecord) -> None: ...

    async def get(
        self, prompt_id: str, version: Optional[int] = None
    ) -> Optional[PromptRecord]:
        """If version is None, return latest."""
        ...

    async def get_versions(self, prompt_id: str) -> List[PromptRecord]:
        """All versions for prompt_id, ordered by version desc."""
        ...


class PromptRegistry:
    """Versioned prompt tracking. Store change_reason, author. Audit every change."""

    def __init__(
        self,
        repository: PromptRegistryRepository,
        audit_logger: AuditLogger,
    ) -> None:
        self._repo = repository
        self._audit = audit_logger

    async def register_prompt(
        self,
        *,
        prompt_id: str,
        name: str,
        content: str,
        change_reason: str,
        author: str,
        tenant_id: str,
        correlation_id: str,
        actor: Optional[str] = None,
    ) -> PromptRecord:
        """Register first version (version 1). Emit audit."""
        actor = actor or author
        record = PromptRecord(
            prompt_id=prompt_id,
            name=name,
            version=1,
            content=content,
            change_reason=change_reason,
            author=author,
            created_at=datetime.now(timezone.utc),
        )
        await self._repo.save(record)
        await self._audit.log_action(
            actor=actor,
            tenant_id=tenant_id,
            action="prompt_registered",
            resource_type="prompt",
            resource_id=f"{prompt_id}@1",
            reason=change_reason,
            correlation_id=correlation_id,
            metadata={"prompt_id": prompt_id, "version": 1, "author": author},
        )
        return record

    async def update_prompt(
        self,
        *,
        prompt_id: str,
        content: str,
        change_reason: str,
        author: str,
        tenant_id: str,
        correlation_id: str,
        actor: Optional[str] = None,
    ) -> PromptRecord:
        """Create new version. Previous versions immutable. Emit audit."""
        actor = actor or author
        existing = await self._repo.get(prompt_id, None)
        if existing is None:
            raise ValueError(f"Prompt not found: {prompt_id}")
        new_version = existing.version + 1
        record = PromptRecord(
            prompt_id=prompt_id,
            name=existing.name,
            version=new_version,
            content=content,
            change_reason=change_reason,
            author=author,
            created_at=datetime.now(timezone.utc),
        )
        await self._repo.save(record)
        await self._audit.log_action(
            actor=actor,
            tenant_id=tenant_id,
            action="prompt_updated",
            resource_type="prompt",
            resource_id=f"{prompt_id}@{new_version}",
            reason=change_reason,
            correlation_id=correlation_id,
            metadata={
                "prompt_id": prompt_id,
                "version": new_version,
                "author": author,
                "previous_version": existing.version,
            },
        )
        return record

    async def get_prompt(
        self,
        prompt_id: str,
        version: Optional[int] = None,
    ) -> Optional[PromptRecord]:
        """Get prompt by id and optional version. If version omitted, returns latest."""
        return await self._repo.get(prompt_id, version)
