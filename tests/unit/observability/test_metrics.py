"""MetricsCollector tests: counters, histogram, tenant separation, failure metrics."""

import threading


from app.observability.metrics import MetricsCollector


def test_metrics_counter_increment():
    """Counter increments correctly."""
    m = MetricsCollector()
    m.increment("request_count")
    m.increment("request_count", 2)
    out = m.export_metrics()
    assert out["counters"]["request_count"] == 3


def test_metrics_histogram_tracks_latency():
    """Histogram tracks latency."""
    m = MetricsCollector()
    m.observe_latency("request_latency", 10.5)
    m.observe_latency("request_latency", 20.0)
    out = m.export_metrics()
    assert "request_latency" in out["histograms"]
    h = out["histograms"]["request_latency"]
    assert h["count"] == 2
    assert h["sum"] == 30.5
    assert 10.5 in h["values"] and 20.0 in h["values"]


def test_metrics_tenant_metrics_separated():
    """Tenant metrics separated."""
    m = MetricsCollector()
    m.increment("request_count", 1, tenant_id="t1")
    m.increment("request_count", 2, tenant_id="t2")
    out = m.export_metrics()
    assert "request_count" in out["counters_by_labels"]
    labels = out["counters_by_labels"]["request_count"]
    assert any("t1" in k for k in labels)
    assert any("t2" in k for k in labels)
    assert sum(labels.values()) == 3


def test_metrics_failure_count_by_category():
    """Failure metrics increment correctly by category."""
    m = MetricsCollector()
    m.increment("failure_count", 1, category="VALIDATION_ERROR")
    m.increment("failure_count", 1, category="VALIDATION_ERROR")
    m.increment("failure_count", 1, category="WORKFLOW_ERROR")
    out = m.export_metrics()
    assert "failure_count" in out["counters_by_labels"]
    labels = out["counters_by_labels"]["failure_count"]
    assert sum(labels.values()) == 3


def test_metrics_observe_latency_with_node_label():
    """Node_execution_latency can be keyed by node."""
    m = MetricsCollector()
    m.observe_latency("node_execution_latency", 5.0, node="retrieval")
    m.observe_latency("node_execution_latency", 10.0, node="decision")
    out = m.export_metrics()
    assert any("retrieval" in k for k in out["histograms"])
    assert any("decision" in k for k in out["histograms"])


def test_metrics_thread_safe():
    """Concurrent increments are safe."""
    m = MetricsCollector()

    def inc():
        for _ in range(100):
            m.increment("workflow_execution_count")

    threads = [threading.Thread(target=inc) for _ in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    out = m.export_metrics()
    assert out["counters"]["workflow_execution_count"] == 1000


def test_metrics_reset():
    """Reset clears all metrics."""
    m = MetricsCollector()
    m.increment("x")
    m.observe_latency("y", 1.0)
    m.reset()
    out = m.export_metrics()
    assert out["counters"] == {}
    assert out["histograms"] == {}
