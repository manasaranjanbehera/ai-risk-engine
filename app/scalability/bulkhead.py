"""Bulkhead: isolate workflow resource pools. Max concurrent tasks, queue overflow protection, prevent tenant starvation."""

import asyncio
from typing import Any, Awaitable, Callable, TypeVar

T = TypeVar("T")


class BulkheadExecutor:
    """
    Limits max concurrent tasks. Bounded queue for waiting; overflow raises.
    Async-safe. Prevents tenant starvation by capping concurrency and queue.
    """

    def __init__(
        self,
        max_concurrent: int = 10,
        max_queued: int = 100,
    ) -> None:
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._max_concurrent = max_concurrent
        self._max_queued = max_queued
        self._queue: asyncio.Queue[
            tuple[
                asyncio.Future[T],
                Callable[..., Awaitable[T]],
                tuple[Any, ...],
                dict[str, Any],
            ]
        ] = asyncio.Queue(maxsize=max_queued)
        self._active = 0
        self._lock = asyncio.Lock()
        self._worker: asyncio.Task[None] | None = None

    @property
    def active_count(self) -> int:
        return self._active

    def _ensure_worker(self) -> None:
        if self._worker is None or self._worker.done():
            self._worker = asyncio.create_task(self._run_worker())

    async def _run_worker(self) -> None:
        while True:
            future, task, args, kwargs = await self._queue.get()
            try:
                async with self._semaphore:
                    async with self._lock:
                        self._active += 1
                    try:
                        result = await task(*args, **kwargs)
                        if not future.done():
                            future.set_result(result)
                    finally:
                        async with self._lock:
                            self._active -= 1
            except Exception as e:
                if not future.done():
                    future.set_exception(e)

    async def submit(
        self,
        task: Callable[..., Awaitable[T]],
        *args: Any,
        **kwargs: Any,
    ) -> T:
        """
        Run task with bulkhead limit. If queue is full, raise. Otherwise enqueue and return when done.
        """
        self._ensure_worker()
        loop = asyncio.get_running_loop()
        future = loop.create_future()
        try:
            self._queue.put_nowait((future, task, args, kwargs))
        except asyncio.QueueFull:
            raise RuntimeError("Bulkhead: max concurrent and queue full") from None
        return await future
