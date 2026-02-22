"""WorkloadPartitioner: deterministic partition mapping."""

import pytest

from app.scalability.workload_partitioning import WorkloadPartitioner


def test_get_partition_deterministic():
    p = WorkloadPartitioner(num_partitions=16)
    a = p.get_partition("tenant-a")
    b = p.get_partition("tenant-a")
    assert a == b


def test_different_tenants_different_partitions():
    p = WorkloadPartitioner(num_partitions=16)
    parts = {p.get_partition(f"tenant-{i}") for i in range(50)}
    assert len(parts) > 1


def test_partition_in_range():
    p = WorkloadPartitioner(num_partitions=10)
    for tenant in ["a", "b", "c", "x", "y", "z"]:
        part = p.get_partition(tenant)
        assert 0 <= part < 10


def test_num_partitions_one():
    p = WorkloadPartitioner(num_partitions=1)
    assert p.get_partition("any") == 0


def test_invalid_partitions_raises():
    with pytest.raises(ValueError, match="num_partitions"):
        WorkloadPartitioner(num_partitions=0)
