"""API middleware: correlation ID, tenant context, audit trigger."""

import json
import logging
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.core.context import correlation_id_ctx, tenant_id_ctx

logger = logging.getLogger(__name__)

TENANT_HEADER = "X-Tenant-ID"
CORRELATION_HEADER = "X-Correlation-ID"
IDEMPOTENCY_HEADER = "X-Idempotency-Key"


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    """Generate or preserve correlation ID; attach to request.state, response header, and logging context."""

    async def dispatch(self, request: Request, call_next) -> Response:
        correlation_id = request.headers.get(CORRELATION_HEADER) or str(uuid.uuid4())
        request.state.correlation_id = correlation_id
        correlation_id_ctx.set(correlation_id)

        response = await call_next(request)
        response.headers[CORRELATION_HEADER] = correlation_id
        return response


class TenantContextMiddleware(BaseHTTPMiddleware):
    """Extract X-Tenant-ID; return 400 if missing; attach to request.state and request-scoped context."""

    async def dispatch(self, request: Request, call_next) -> Response:
        tenant_id = request.headers.get(TENANT_HEADER)
        if not tenant_id or not tenant_id.strip():
            return JSONResponse(
                status_code=400,
                content={"detail": "X-Tenant-ID header is required"},
            )
        request.state.tenant_id = tenant_id.strip()
        tenant_id_ctx.set(request.state.tenant_id)
        return await call_next(request)


class AuditTriggerMiddleware(BaseHTTPMiddleware):
    """After response: log structured audit event (correlation_id, tenant_id, path, method, status_code)."""

    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)
        correlation_id = getattr(request.state, "correlation_id", None)
        tenant_id = getattr(request.state, "tenant_id", None)
        audit_event = {
            "event": "request_audit",
            "correlation_id": correlation_id,
            "tenant_id": tenant_id,
            "path": request.url.path,
            "method": request.method,
            "status_code": response.status_code,
        }
        logger.info(json.dumps(audit_event))
        return response
