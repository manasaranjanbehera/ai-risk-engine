"""Prometheus-style metrics collector. Thread-safe, in-memory. No real Prometheus dependency."""

import threading
from typing import Any


class MetricsCollector:
    """
    In-memory Prometheus-style registry. Tracks counters and histograms.
    Thread-safe. Exposes increment, observe_latency, export_metrics.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        # Counters: name -> value or name -> {labels_hash -> value}
        self._counters: dict[str, float] = {}
        self._counters_by_labels: dict[str, dict[str, float]] = {}
        # Histograms: name -> list of observed values (for latency)
        self._histograms: dict[str, list[float]] = {}

    def increment(
        self,
        name: str,
        value: float = 1.0,
        *,
        tenant_id: str | None = None,
        category: str | None = None,
    ) -> None:
        """Increment a counter. Optional tenant_id or category for dimensional metrics."""
        with self._lock:
            if tenant_id is not None:
                key = f"{name}:tenant={tenant_id}"
                self._counters_by_labels.setdefault(name, {})[key] = (
                    self._counters_by_labels.get(name, {}).get(key, 0) + value
                )
            elif category is not None:
                key = f"{name}:category={category}"
                self._counters_by_labels.setdefault(name, {})[key] = (
                    self._counters_by_labels.get(name, {}).get(key, 0) + value
                )
            else:
                self._counters[name] = self._counters.get(name, 0) + value

    def observe_latency(
        self,
        name: str,
        latency_ms: float,
        *,
        node: str | None = None,
    ) -> None:
        """Record a latency observation (histogram-style). Optional node label."""
        with self._lock:
            bucket = f"{name}" if node is None else f"{name}:node={node}"
            if bucket not in self._histograms:
                self._histograms[bucket] = []
            self._histograms[bucket].append(latency_ms)

    def export_metrics(self) -> dict[str, Any]:
        """Export all metrics as a dict (simulated Prometheus-style)."""
        with self._lock:
            out: dict[str, Any] = {
                "counters": dict(self._counters),
                "counters_by_labels": {
                    k: dict(v) for k, v in self._counters_by_labels.items()
                },
                "histograms": {
                    k: {
                        "count": len(v),
                        "sum": sum(v),
                        "values": v,
                    }
                    for k, v in self._histograms.items()
                },
            }
            return out

    def reset(self) -> None:
        """Reset all metrics (for tests)."""
        with self._lock:
            self._counters.clear()
            self._counters_by_labels.clear()
            self._histograms.clear()
