# app/main.py


from fastapi import FastAPI
from fastapi.responses import JSONResponse

from app.api.middleware import (
    AuditTriggerMiddleware,
    CorrelationIdMiddleware,
    TenantContextMiddleware,
)
from app.api.routers import compliance, events, health, risk, tenant
from app.config.logging import configure_logging
from app.config.settings import get_settings
from app.application.exceptions import ApplicationError, MessagingFailureError
from app.domain.exceptions import DomainError, DomainValidationError

settings = get_settings()
configure_logging(settings.log_level)

app = FastAPI(
    title=settings.app_name,
    version=settings.version,
    debug=settings.debug,
)

# Middleware order: last added runs first (outermost). Request flow: CorrelationId -> TenantContext -> AuditTrigger.
app.add_middleware(AuditTriggerMiddleware)
app.add_middleware(TenantContextMiddleware)
app.add_middleware(CorrelationIdMiddleware)


@app.exception_handler(DomainValidationError)
async def domain_validation_error_handler(request, exc: DomainValidationError):
    return JSONResponse(status_code=422, content={"detail": exc.message})


@app.exception_handler(DomainError)
async def domain_error_handler(request, exc: DomainError):
    return JSONResponse(status_code=400, content={"detail": exc.message})


@app.exception_handler(MessagingFailureError)
async def messaging_failure_error_handler(request, exc: MessagingFailureError):
    return JSONResponse(status_code=503, content={"detail": exc.message})


@app.exception_handler(ApplicationError)
async def application_error_handler(request, exc: ApplicationError):
    return JSONResponse(status_code=500, content={"detail": exc.message})


@app.exception_handler(Exception)
async def unexpected_error_handler(request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
    )


# Routers: /health, /tenant, /events, /risk, /compliance
app.include_router(health.router)
app.include_router(tenant.router, prefix="/tenant")
app.include_router(events.router, prefix="/events")
app.include_router(risk.router, prefix="/risk")
app.include_router(compliance.router, prefix="/compliance")
