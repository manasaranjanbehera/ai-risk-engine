# app/api/routers/health.py

from fastapi import APIRouter, Request

from app.config.settings import get_settings

router = APIRouter()


@router.get("/health")
async def health(request: Request):
    """Health check with tenant and correlation ID from request state."""
    settings = get_settings()
    return {
        "status": "ok",
        "tenant_id": request.state.tenant_id,
        "correlation_id": request.state.correlation_id,
        "environment": settings.environment,
        "version": settings.version,
    }
