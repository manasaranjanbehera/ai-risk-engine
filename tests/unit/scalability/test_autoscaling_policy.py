"""AutoScalingPolicy: deterministic SCALE_UP, SCALE_DOWN, NO_ACTION."""

from app.scalability.autoscaling_policy import (
    AutoScalingPolicy,
    MetricsSnapshot,
    ScalingAction,
)


def test_scale_up_cpu():
    policy = AutoScalingPolicy(cpu_scale_up_threshold=70.0, max_replicas=10)
    m = MetricsSnapshot(cpu_usage_pct=80.0, current_replicas=2)
    d = policy.evaluate(m)
    assert d.action == ScalingAction.SCALE_UP
    assert "cpu" in d.reason.lower()


def test_scale_up_latency():
    policy = AutoScalingPolicy(latency_scale_up_ms=500.0, max_replicas=10)
    m = MetricsSnapshot(request_latency_p99_ms=600.0, current_replicas=1)
    d = policy.evaluate(m)
    assert d.action == ScalingAction.SCALE_UP


def test_scale_up_failure_rate():
    policy = AutoScalingPolicy(failure_rate_scale_up=0.05, max_replicas=10)
    m = MetricsSnapshot(failure_rate=0.1, current_replicas=1)
    d = policy.evaluate(m)
    assert d.action == ScalingAction.SCALE_UP


def test_scale_up_queue_depth():
    policy = AutoScalingPolicy(queue_depth_scale_up=50, max_replicas=10)
    m = MetricsSnapshot(queue_depth=60, current_replicas=1)
    d = policy.evaluate(m)
    assert d.action == ScalingAction.SCALE_UP


def test_no_action_at_max_replicas():
    policy = AutoScalingPolicy(cpu_scale_up_threshold=70.0, max_replicas=2)
    m = MetricsSnapshot(cpu_usage_pct=90.0, current_replicas=2)
    d = policy.evaluate(m)
    assert d.action == ScalingAction.NO_ACTION


def test_scale_down_when_all_low():
    policy = AutoScalingPolicy(
        cpu_scale_down_threshold=30.0,
        min_replicas=1,
        max_replicas=10,
    )
    m = MetricsSnapshot(
        cpu_usage_pct=20.0,
        request_latency_p99_ms=100.0,
        failure_rate=0.0,
        queue_depth=0,
        current_replicas=3,
    )
    d = policy.evaluate(m)
    assert d.action == ScalingAction.SCALE_DOWN


def test_no_action_at_min_replicas():
    policy = AutoScalingPolicy(min_replicas=1)
    m = MetricsSnapshot(cpu_usage_pct=10.0, current_replicas=1)
    d = policy.evaluate(m)
    assert d.action == ScalingAction.NO_ACTION
    assert "min_replicas" in d.reason.lower()


def test_deterministic_same_input_same_output():
    policy = AutoScalingPolicy()
    m = MetricsSnapshot(cpu_usage_pct=50.0, current_replicas=2)
    d1 = policy.evaluate(m)
    d2 = policy.evaluate(m)
    assert d1.action == d2.action and d1.reason == d2.reason
