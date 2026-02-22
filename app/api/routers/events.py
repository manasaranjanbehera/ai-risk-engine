"""Events API router: POST /events (idempotent), GET /events/{event_id}."""

import uuid
from datetime import datetime, timezone
from typing import Annotated, Optional, Union

from fastapi import APIRouter, Depends, Header, Request, Response
from fastapi.responses import JSONResponse

from app.api.dependencies import get_correlation_id, get_event_service, get_tenant_id
from app.application.event_service import EventService
from app.application.exceptions import ApplicationError, MessagingFailureError
from app.domain.exceptions import DomainError, DomainValidationError
from app.domain.models.event import ComplianceEvent, EventStatus, RiskEvent
from app.domain.schemas.event import (
    ComplianceEventCreateRequest,
    EventResponse,
    RiskEventCreateRequest,
)
from app.domain.validators.event_validator import (
    validate_compliance_event_create_request,
    validate_risk_event_create_request,
)

router = APIRouter()


def _request_to_risk_event(tenant_id: str, req: RiskEventCreateRequest) -> RiskEvent:
    """Build validated domain RiskEvent from API request. Validation already done in API layer."""
    event_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    metadata = (req.metadata or {}).copy()
    if req.version:
        metadata["version"] = req.version
    return RiskEvent(
        event_id=event_id,
        tenant_id=tenant_id,
        status=EventStatus.CREATED,
        created_at=now,
        metadata=metadata or None,
        risk_score=req.risk_score,
        category=req.category,
    )


def _request_to_compliance_event(
    tenant_id: str, req: ComplianceEventCreateRequest
) -> ComplianceEvent:
    """Build validated domain ComplianceEvent from API request."""
    event_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    metadata = (req.metadata or {}).copy()
    if req.version:
        metadata["version"] = req.version
    return ComplianceEvent(
        event_id=event_id,
        tenant_id=tenant_id,
        status=EventStatus.CREATED,
        created_at=now,
        metadata=metadata or None,
        regulation_ref=req.regulation_ref,
        compliance_type=req.compliance_type,
    )


@router.post("/", response_model=EventResponse)
async def create_event(
    request: Request,
    body: Union[RiskEventCreateRequest, ComplianceEventCreateRequest],
    x_idempotency_key: Annotated[
        Optional[str], Header(alias="X-Idempotency-Key")
    ] = None,
    tenant_id: Annotated[str, Depends(get_tenant_id)] = ...,
    correlation_id: Annotated[str, Depends(get_correlation_id)] = ...,
    event_service: Annotated[EventService, Depends(get_event_service)] = ...,
):
    """Create event (risk or compliance). Idempotent via X-Idempotency-Key. Domain validation at API layer."""
    if not x_idempotency_key or not x_idempotency_key.strip():
        return JSONResponse(
            status_code=400,
            content={"detail": "X-Idempotency-Key header is required"},
        )
    idempotency_key = x_idempotency_key.strip()

    if isinstance(body, RiskEventCreateRequest):
        validate_risk_event_create_request(body)
        event = _request_to_risk_event(tenant_id, body)
    else:
        validate_compliance_event_create_request(body)
        event = _request_to_compliance_event(tenant_id, body)

    try:
        response = await event_service.create_event(
            event=event,
            tenant_id=tenant_id,
            idempotency_key=idempotency_key,
            correlation_id=correlation_id,
        )
    except DomainValidationError as e:
        return JSONResponse(status_code=422, content={"detail": e.message})
    except DomainError as e:
        return JSONResponse(status_code=400, content={"detail": e.message})
    except MessagingFailureError as e:
        return JSONResponse(status_code=503, content={"detail": e.message})
    except ApplicationError as e:
        return JSONResponse(status_code=500, content={"detail": e.message})

    return Response(content=response.model_dump_json(), media_type="application/json")


@router.get("/{event_id}", response_model=EventResponse)
async def get_event(
    event_id: str,
    tenant_id: Annotated[str, Depends(get_tenant_id)] = ...,
    event_service: Annotated[EventService, Depends(get_event_service)] = ...,
):
    """Get event by ID (tenant-scoped)."""
    event = await event_service.get_event(tenant_id, event_id)
    if event is None:
        return JSONResponse(status_code=404, content={"detail": "Event not found"})
    return event
