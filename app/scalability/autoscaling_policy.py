"""Auto-scaling policy: deterministic scaling decisions from metrics snapshot."""

from dataclasses import dataclass
from enum import Enum


class ScalingAction(str, Enum):
    SCALE_UP = "scale_up"
    SCALE_DOWN = "scale_down"
    NO_ACTION = "no_action"


@dataclass
class ScalingDecision:
    action: ScalingAction
    reason: str


@dataclass
class MetricsSnapshot:
    """Input for scaling evaluation. All values optional; missing => no signal."""

    cpu_usage_pct: float | None = None
    request_latency_p99_ms: float | None = None
    failure_rate: float | None = None
    queue_depth: int | None = None
    current_replicas: int = 1


class AutoScalingPolicy:
    """
    Deterministic scaling: CPU, latency, failure rate, queue depth.
    Returns SCALE_UP, SCALE_DOWN, or NO_ACTION.
    """

    def __init__(
        self,
        cpu_scale_up_threshold: float = 70.0,
        cpu_scale_down_threshold: float = 30.0,
        latency_scale_up_ms: float = 500.0,
        failure_rate_scale_up: float = 0.05,
        queue_depth_scale_up: int = 50,
        min_replicas: int = 1,
        max_replicas: int = 20,
    ) -> None:
        self._cpu_up = cpu_scale_up_threshold
        self._cpu_down = cpu_scale_down_threshold
        self._latency_up = latency_scale_up_ms
        self._failure_up = failure_rate_scale_up
        self._queue_up = queue_depth_scale_up
        self._min_replicas = min_replicas
        self._max_replicas = max_replicas

    def evaluate(self, metrics: MetricsSnapshot) -> ScalingDecision:
        """Fully deterministic. Prefer scale-up on any breach; scale-down only when all low."""
        m = metrics
        # Scale-up conditions (any can trigger)
        if m.cpu_usage_pct is not None and m.cpu_usage_pct >= self._cpu_up:
            if m.current_replicas < self._max_replicas:
                return ScalingDecision(
                    ScalingAction.SCALE_UP,
                    f"cpu_usage={m.cpu_usage_pct}% >= {self._cpu_up}%",
                )
        if (
            m.request_latency_p99_ms is not None
            and m.request_latency_p99_ms >= self._latency_up
        ):
            if m.current_replicas < self._max_replicas:
                return ScalingDecision(
                    ScalingAction.SCALE_UP,
                    f"latency_p99={m.request_latency_p99_ms}ms >= {self._latency_up}ms",
                )
        if m.failure_rate is not None and m.failure_rate >= self._failure_up:
            if m.current_replicas < self._max_replicas:
                return ScalingDecision(
                    ScalingAction.SCALE_UP,
                    f"failure_rate={m.failure_rate} >= {self._failure_up}",
                )
        if m.queue_depth is not None and m.queue_depth >= self._queue_up:
            if m.current_replicas < self._max_replicas:
                return ScalingDecision(
                    ScalingAction.SCALE_UP,
                    f"queue_depth={m.queue_depth} >= {self._queue_up}",
                )
        # Scale-down: all signals low and we have room to shrink
        if m.current_replicas <= self._min_replicas:
            return ScalingDecision(ScalingAction.NO_ACTION, "at min_replicas")
        cpu_low = m.cpu_usage_pct is None or m.cpu_usage_pct <= self._cpu_down
        latency_low = (
            m.request_latency_p99_ms is None
            or m.request_latency_p99_ms < self._latency_up * 0.5
        )
        failure_low = m.failure_rate is None or m.failure_rate < self._failure_up * 0.5
        queue_low = m.queue_depth is None or m.queue_depth < self._queue_up * 0.5
        if cpu_low and latency_low and failure_low and queue_low:
            return ScalingDecision(
                ScalingAction.SCALE_DOWN, "all metrics below scale-down thresholds"
            )
        return ScalingDecision(ScalingAction.NO_ACTION, "no scaling signal")
