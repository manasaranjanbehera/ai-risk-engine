"""Scalability layer: distributed locking, rate limiting, circuit breaker, bulkhead, autoscaling, partitioning, health. No FastAPI."""

from app.scalability.autoscaling_policy import (
    AutoScalingPolicy,
    MetricsSnapshot,
    ScalingAction,
    ScalingDecision,
)
from app.scalability.bulkhead import BulkheadExecutor
from app.scalability.circuit_breaker import CircuitBreaker, CircuitState
from app.scalability.distributed_lock import DistributedLock
from app.scalability.health_monitor import HealthMonitor
from app.scalability.rate_limiter import TenantRateLimiter
from app.scalability.workload_partitioning import WorkloadPartitioner

__all__ = [
    "AutoScalingPolicy",
    "BulkheadExecutor",
    "CircuitBreaker",
    "CircuitState",
    "DistributedLock",
    "HealthMonitor",
    "MetricsSnapshot",
    "ScalingAction",
    "ScalingDecision",
    "TenantRateLimiter",
    "WorkloadPartitioner",
]
