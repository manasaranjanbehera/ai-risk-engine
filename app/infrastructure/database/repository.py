# app/infrastructure/database/repository.py

from typing import Generic, Optional, Type, TypeVar

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

T = TypeVar("T")


class AsyncRepository(Generic[T]):
    def __init__(self, model: Type[T]):
        self.model = model

    async def get_by_id(
        self,
        db: AsyncSession,
        id,
        tenant_id: str,
    ) -> Optional[T]:

        stmt = select(self.model).where(
            self.model.id == id,
            self.model.tenant_id == tenant_id,
            self.model.is_deleted.is_(False),
        )

        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def create(
        self,
        db: AsyncSession,
        obj: T,
    ) -> T:
        db.add(obj)
        await db.commit()
        await db.refresh(obj)
        return obj

    async def upsert_idempotent(
        self,
        db: AsyncSession,
        values: dict,
        idempotency_key: str,
        tenant_id: str,
    ) -> T:
        # Ensure tenant_id and idempotency_key are always set from method args
        # so the table's non-nullable tenant_id is satisfied and tenant isolation is enforced.
        payload = {**values, "tenant_id": tenant_id, "idempotency_key": idempotency_key}

        stmt = insert(self.model).values(**payload)

        # On conflict, update only non-key columns; do not overwrite tenant_id or idempotency_key.
        set_on_conflict = {
            k: v
            for k, v in payload.items()
            if k not in ("tenant_id", "idempotency_key")
        }
        stmt = stmt.on_conflict_do_update(
            index_elements=["idempotency_key"],
            set_=set_on_conflict,
        ).returning(self.model)

        result = await db.execute(stmt)
        await db.commit()

        return result.fetchone()[0]

    async def list_by_tenant(
        self,
        db: AsyncSession,
        tenant_id: str,
    ):
        stmt = select(self.model).where(
            self.model.tenant_id == tenant_id,
            self.model.is_deleted.is_(False),
        )

        result = await db.execute(stmt)
        return result.scalars().all()
