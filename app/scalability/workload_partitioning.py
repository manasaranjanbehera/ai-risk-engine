"""Tenant-aware workload partitioning. Consistent hashing, stable partition mapping."""

import hashlib


class WorkloadPartitioner:
    """
    Maps tenant_id to a stable partition index using consistent hashing (hash-based).
    Deterministic: same tenant_id always maps to same partition.
    """

    def __init__(self, num_partitions: int = 16) -> None:
        if num_partitions < 1:
            raise ValueError("num_partitions must be >= 1")
        self._num_partitions = num_partitions

    def get_partition(self, tenant_id: str) -> int:
        """Return partition index in [0, num_partitions - 1]. Stable for same tenant_id."""
        h = hashlib.sha256(tenant_id.encode("utf-8")).hexdigest()
        return int(h, 16) % self._num_partitions
