import asyncio
import inspect
from typing import Any, Callable, Optional


class BackgroundJobService:
    def __init__(self):
        self._queue: asyncio.Queue[tuple[Callable[..., Any], tuple[Any, ...], dict[str, Any]]] = asyncio.Queue()
        self._task: Optional[asyncio.Task] = None

    async def start(self) -> None:
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(self._worker())

    async def stop(self) -> None:
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

    async def enqueue(self, func: Callable[..., Any], *args: Any, **kwargs: Any) -> None:
        await self.start()
        await self._queue.put((func, args, kwargs))

    async def _worker(self) -> None:
        while True:
            func, args, kwargs = await self._queue.get()
            try:
                result = func(*args, **kwargs)
                if inspect.isawaitable(result):
                    await result
            except Exception as exc:  # pragma: no cover - runtime guard
                print(f"[BACKGROUND_JOB] error: {exc}")
            finally:
                self._queue.task_done()


background_jobs = BackgroundJobService()
