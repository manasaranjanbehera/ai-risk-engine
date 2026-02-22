"""OpenTelemetry-style tracing. In-memory exporter. Async-compatible."""

import uuid
from contextlib import asynccontextmanager
from typing import AsyncContextManager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass
class Span:
    """Single span with timing and attributes."""

    span_id: str
    trace_id: str
    name: str
    parent_span_id: str | None
    start_time_utc: datetime
    end_time_utc: datetime | None = None
    attributes: dict[str, Any] = field(default_factory=dict)

    @property
    def duration_ms(self) -> float | None:
        if self.end_time_utc is None:
            return None
        delta = self.end_time_utc - self.start_time_utc
        return delta.total_seconds() * 1000


@dataclass
class Trace:
    """Trace with root span and children."""

    trace_id: str
    spans: list[Span] = field(default_factory=list)

    def get_span(self, span_id: str) -> Span | None:
        for s in self.spans:
            if s.span_id == span_id:
                return s
        return None


class TracingService:
    """
    In-memory tracing. start_span/end_span with trace ID propagation,
    span hierarchy (workflow → nodes), latency, and metadata.
    No real OTLP export.
    """

    def __init__(self) -> None:
        self._traces: list[Trace] = []
        self._active_spans: dict[str, Span] = {}  # span_id -> span
        self._span_stack: list[str] = []  # current span chain for nesting

    def _now_utc(self) -> datetime:
        return datetime.now(timezone.utc)

    @asynccontextmanager
    async def start_span(
        self,
        name: str,
        *,
        trace_id: str | None = None,
        parent_span_id: str | None = None,
        tenant_id: str | None = None,
        correlation_id: str | None = None,
        model_version: str | None = None,
        prompt_version: int | None = None,
    ) -> AsyncContextManager[Span]:
        """
        Start a span. If trace_id is None, create a new trace. Returns the span; on exit, end the span.
        """
        span_id = str(uuid.uuid4())
        if trace_id is None:
            trace_id = str(uuid.uuid4())
        start = self._now_utc()
        attrs: dict[str, Any] = {}
        if tenant_id is not None:
            attrs["tenant_id"] = tenant_id
        if correlation_id is not None:
            attrs["correlation_id"] = correlation_id
        if model_version is not None:
            attrs["model_version"] = model_version
        if prompt_version is not None:
            attrs["prompt_version"] = prompt_version

        span = Span(
            span_id=span_id,
            trace_id=trace_id,
            name=name,
            parent_span_id=parent_span_id,
            start_time_utc=start,
            attributes=attrs,
        )
        self._active_spans[span_id] = span
        self._span_stack.append(span_id)

        # Ensure we have a trace for this trace_id
        existing = next((t for t in self._traces if t.trace_id == trace_id), None)
        if existing is None:
            existing = Trace(trace_id=trace_id)
            self._traces.append(existing)
        existing.spans.append(span)

        try:
            yield span
        finally:
            span.end_time_utc = self._now_utc()
            if self._span_stack and self._span_stack[-1] == span_id:
                self._span_stack.pop()
            self._active_spans.pop(span_id, None)

    def get_traces(self) -> list[Trace]:
        """Return all stored traces (for tests/export)."""
        return list(self._traces)

    def get_trace(self, trace_id: str) -> Trace | None:
        return next((t for t in self._traces if t.trace_id == trace_id), None)

    def reset(self) -> None:
        """Clear stored traces (for tests)."""
        self._traces.clear()
        self._active_spans.clear()
        self._span_stack.clear()
