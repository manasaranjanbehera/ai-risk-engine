# app/core/context.py

import contextvars

correlation_id_ctx = contextvars.ContextVar("correlation_id", default=None)
tenant_id_ctx = contextvars.ContextVar("tenant_id", default=None)
