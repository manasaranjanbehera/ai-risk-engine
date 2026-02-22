"""BulkheadExecutor: concurrency caps, queue overflow."""

import asyncio

import pytest

from app.scalability.bulkhead import BulkheadExecutor


@pytest.mark.asyncio
async def test_submit_runs_task():
    bulk = BulkheadExecutor(max_concurrent=2, max_queued=5)

    async def task():
        return 99

    result = await bulk.submit(task)
    assert result == 99


@pytest.mark.asyncio
async def test_concurrency_cap():
    bulk = BulkheadExecutor(max_concurrent=2, max_queued=10)
    running = 0
    max_running = 0
    lock = asyncio.Lock()

    async def work():
        nonlocal running, max_running
        async with lock:
            running += 1
            max_running = max(max_running, running)
        await asyncio.sleep(0.05)
        async with lock:
            running -= 1
        return 1

    tasks = [bulk.submit(work) for _ in range(5)]
    results = await asyncio.gather(*tasks)
    assert len(results) == 5
    assert max_running <= 2


@pytest.mark.asyncio
async def test_queue_overflow_raises():
    """With max_concurrent=1 and max_queued=1, only 2 tasks can be in flight; 3rd submit raises."""
    bulk = BulkheadExecutor(max_concurrent=1, max_queued=1)
    results = []

    async def slow():
        await asyncio.sleep(0.05)
        return 1

    async def submit_and_capture():
        try:
            r = await bulk.submit(slow)
            results.append(("ok", r))
        except RuntimeError as e:
            results.append(("err", str(e)))

    # Run 3 submits concurrently; at least one must hit queue full (overflow protection).
    await asyncio.gather(
        submit_and_capture(),
        submit_and_capture(),
        submit_and_capture(),
    )
    errs = [r for r in results if r[0] == "err"]
    oks = [r for r in results if r[0] == "ok"]
    assert len(errs) >= 1, f"expected at least one queue full error, got {results}"
    assert len(oks) >= 1, f"expected at least one success, got {results}"
    assert all("queue full" in e[1].lower() for e in errs)
