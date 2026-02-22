"""Model version and approval status tracking. No FastAPI."""

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Optional, Protocol

from app.governance.audit_logger import AuditLogger
from app.governance.exceptions import InvalidModelStateError, ModelNotApprovedError


class ModelStatus(str, Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


@dataclass(frozen=True)
class ModelRecord:
    """Registered model with approval state. Immutable."""

    model_name: str
    version: str
    checksum: str
    created_at: datetime
    approved: bool
    approved_by: Optional[str]
    approved_at: Optional[datetime]
    status: ModelStatus

    def is_deployable(self) -> bool:
        """Cannot deploy unapproved model."""
        return self.status == ModelStatus.APPROVED and self.approved


class ModelRegistryRepository(Protocol):
    """Storage for model records."""

    async def save(self, record: ModelRecord) -> None: ...

    async def get(self, model_name: str, version: str) -> Optional[ModelRecord]: ...

    async def get_latest(self, model_name: str) -> Optional[ModelRecord]: ...


class ModelRegistry:
    """Track model versions and approval status. Approval emits audit log."""

    def __init__(
        self,
        repository: ModelRegistryRepository,
        audit_logger: AuditLogger,
    ) -> None:
        self._repo = repository
        self._audit = audit_logger

    async def register_model(
        self,
        *,
        model_name: str,
        version: str,
        checksum: str,
        correlation_id: str,
        tenant_id: str,
    ) -> ModelRecord:
        """Register a new model version. Status PENDING."""
        record = ModelRecord(
            model_name=model_name,
            version=version,
            checksum=checksum,
            created_at=datetime.now(timezone.utc),
            approved=False,
            approved_by=None,
            approved_at=None,
            status=ModelStatus.PENDING,
        )
        await self._repo.save(record)
        return record

    async def approve_model(
        self,
        *,
        model_name: str,
        version: str,
        approved_by: str,
        tenant_id: str,
        correlation_id: str,
        reason: Optional[str] = None,
    ) -> ModelRecord:
        """Approve model. Emit audit log. Cannot approve twice."""
        existing = await self._repo.get(model_name, version)
        if existing is None:
            raise InvalidModelStateError(f"Model not found: {model_name}@{version}")
        if existing.status == ModelStatus.APPROVED:
            raise InvalidModelStateError(
                f"Model already approved: {model_name}@{version}"
            )
        if existing.status == ModelStatus.REJECTED:
            raise InvalidModelStateError(
                f"Cannot approve rejected model: {model_name}@{version}"
            )
        approved_record = ModelRecord(
            model_name=existing.model_name,
            version=existing.version,
            checksum=existing.checksum,
            created_at=existing.created_at,
            approved=True,
            approved_by=approved_by,
            approved_at=datetime.now(timezone.utc),
            status=ModelStatus.APPROVED,
        )
        await self._repo.save(approved_record)
        await self._audit.log_action(
            actor=approved_by,
            tenant_id=tenant_id,
            action="model_approved",
            resource_type="model",
            resource_id=f"{model_name}@{version}",
            reason=reason,
            correlation_id=correlation_id,
            metadata={"model_name": model_name, "version": version},
        )
        return approved_record

    async def reject_model(
        self,
        *,
        model_name: str,
        version: str,
        rejected_by: str,
        tenant_id: str,
        correlation_id: str,
        reason: Optional[str] = None,
    ) -> ModelRecord:
        """Reject model. Emit audit log."""
        existing = await self._repo.get(model_name, version)
        if existing is None:
            raise InvalidModelStateError(f"Model not found: {model_name}@{version}")
        if existing.status == ModelStatus.REJECTED:
            raise InvalidModelStateError(
                f"Model already rejected: {model_name}@{version}"
            )
        rejected_record = ModelRecord(
            model_name=existing.model_name,
            version=existing.version,
            checksum=existing.checksum,
            created_at=existing.created_at,
            approved=False,
            approved_by=None,
            approved_at=None,
            status=ModelStatus.REJECTED,
        )
        await self._repo.save(rejected_record)
        await self._audit.log_action(
            actor=rejected_by,
            tenant_id=tenant_id,
            action="model_rejected",
            resource_type="model",
            resource_id=f"{model_name}@{version}",
            reason=reason,
            correlation_id=correlation_id,
            metadata={"model_name": model_name, "version": version},
        )
        return rejected_record

    async def get_model(
        self,
        model_name: str,
        version: Optional[str] = None,
    ) -> Optional[ModelRecord]:
        """Get model record. If version omitted, returns latest."""
        if version:
            return await self._repo.get(model_name, version)
        return await self._repo.get_latest(model_name)

    async def get_approved_model(
        self,
        model_name: str,
        version: Optional[str] = None,
    ) -> ModelRecord:
        """Get model and enforce approval. Raises ModelNotApprovedError if not approved."""
        record = await self.get_model(model_name, version)
        if record is None:
            raise ModelNotApprovedError(f"Model not found: {model_name}")
        if not record.is_deployable():
            raise ModelNotApprovedError(
                f"Cannot deploy unapproved model: {model_name}@{record.version}"
            )
        return record
