"""TracingService tests: trace ID, span nesting, latency, metadata."""

import pytest

from app.observability.tracing import TracingService


@pytest.mark.asyncio
async def test_tracing_creates_trace_id():
    """Trace ID created when starting span."""
    t = TracingService()
    async with t.start_span("root") as span:
        assert span.span_id
        assert span.trace_id
    traces = t.get_traces()
    assert len(traces) == 1
    assert traces[0].trace_id == span.trace_id


@pytest.mark.asyncio
async def test_tracing_span_nesting():
    """Span nesting correct (workflow → nodes)."""
    t = TracingService()
    async with t.start_span("workflow") as root:
        trace_id = root.trace_id
        parent_id = root.span_id
        async with t.start_span(
            "node_a", trace_id=trace_id, parent_span_id=parent_id
        ) as child:
            assert child.parent_span_id == parent_id
            assert child.trace_id == trace_id
    traces = t.get_traces()
    assert len(traces) == 1
    assert len(traces[0].spans) == 2


@pytest.mark.asyncio
async def test_tracing_latency_recorded():
    """Latency recorded on span end."""
    t = TracingService()
    async with t.start_span("s1") as span:
        pass
    assert span.end_time_utc is not None
    assert span.duration_ms is not None
    assert span.duration_ms >= 0


@pytest.mark.asyncio
async def test_tracing_metadata_attached():
    """Metadata (tenant_id, correlation_id, model_version, prompt_version) attached."""
    t = TracingService()
    async with t.start_span(
        "s1",
        tenant_id="t1",
        correlation_id="c1",
        model_version="v1",
        prompt_version=2,
    ) as span:
        pass
    assert span.attributes.get("tenant_id") == "t1"
    assert span.attributes.get("correlation_id") == "c1"
    assert span.attributes.get("model_version") == "v1"
    assert span.attributes.get("prompt_version") == 2


@pytest.mark.asyncio
async def test_tracing_reset():
    """Reset clears stored traces."""
    t = TracingService()
    async with t.start_span("s1"):
        pass
    t.reset()
    assert len(t.get_traces()) == 0
