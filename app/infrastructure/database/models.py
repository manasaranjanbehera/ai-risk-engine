# app/infrastructure/database/models.py

import uuid

from sqlalchemy import Boolean, Column, DateTime, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.sql import func

from app.infrastructure.database.session import Base


class BaseModel(Base):
    __abstract__ = True

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    tenant_id = Column(String, nullable=False, index=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    created_by = Column(String, nullable=True)
    updated_by = Column(String, nullable=True)

    is_deleted = Column(Boolean, default=False)


class TestEvent(BaseModel):
    __tablename__ = "test_events"

    name = Column(String)
    idempotency_key = Column(String, unique=True)


class Event(BaseModel):
    """ORM model for persisted domain events (application boundary, status RECEIVED)."""

    __tablename__ = "events"

    event_id = Column(String, nullable=False, index=True)
    correlation_id = Column(String, nullable=False)
    status = Column(String, nullable=False, default="received")
    event_type = Column(String, nullable=False)
    metadata_ = Column("metadata", JSONB, nullable=True)
    version = Column(String, nullable=False, default="1.0")
