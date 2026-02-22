"""Pydantic schemas for event API and serialization. Strict validation, no DB or infrastructure."""

import json
from datetime import datetime
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field, field_validator

from app.domain.models.event import EventStatus

# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------


class RiskEventCreateRequest(BaseModel):
    """Request schema for creating a risk event. No DB-specific fields."""

    tenant_id: str = Field(
        ..., min_length=1, description="Tenant identifier; must not be empty"
    )
    risk_score: Optional[float] = Field(
        None, ge=0.0, le=100.0, description="Risk score in 0–100"
    )
    category: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = Field(
        None, description="JSON-serializable metadata"
    )
    version: str = Field(..., min_length=1, description="Schema/API version")

    @field_validator("metadata")
    @classmethod
    def metadata_must_be_json_serializable(
        cls, v: Optional[Dict[str, Any]]
    ) -> Optional[Dict[str, Any]]:
        """Ensure metadata is JSON-serializable (dict with str keys and JSON-serializable values)."""
        if v is None:
            return v
        try:
            json.dumps(v)
        except (TypeError, ValueError) as e:
            raise ValueError("metadata must be JSON-serializable") from e
        return v


class ComplianceEventCreateRequest(BaseModel):
    """Request schema for creating a compliance event. No DB-specific fields."""

    tenant_id: str = Field(
        ..., min_length=1, description="Tenant identifier; must not be empty"
    )
    regulation_ref: Optional[str] = None
    compliance_type: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = Field(
        None, description="JSON-serializable metadata"
    )
    version: str = Field(..., min_length=1, description="Schema/API version")

    @field_validator("metadata")
    @classmethod
    def metadata_must_be_json_serializable(
        cls, v: Optional[Dict[str, Any]]
    ) -> Optional[Dict[str, Any]]:
        """Ensure metadata is JSON-serializable."""
        if v is None:
            return v
        try:
            json.dumps(v)
        except (TypeError, ValueError) as e:
            raise ValueError("metadata must be JSON-serializable") from e
        return v


# ---------------------------------------------------------------------------
# Response schema
# ---------------------------------------------------------------------------


class EventResponse(BaseModel):
    """Response schema for event read. Explicit typing, versioned."""

    event_id: str
    tenant_id: str
    status: EventStatus
    created_at: datetime
    metadata: Optional[Dict[str, Any]] = None
    version: str = Field(..., min_length=1, description="Schema/API version")

    model_config = {"from_attributes": True}
