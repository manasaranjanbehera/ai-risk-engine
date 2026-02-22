# app/api/routers/tenant.py

from fastapi import APIRouter, Request

router = APIRouter()


@router.get("/context")
async def tenant_context(request: Request):
    """Return current tenant and correlation ID for debugging tenant propagation."""
    return {
        "tenant_id": request.state.tenant_id,
        "correlation_id": request.state.correlation_id,
    }
