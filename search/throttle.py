# search/throttle.py
import asyncio


class AsyncThrottle:
    """并发上限 + 请求最小间隔的异步限流器。"""

    def __init__(self, max_concurrency: int, min_interval: float):
        self._sem = asyncio.Semaphore(max(1, max_concurrency))
        self._min_interval = max(0.0, min_interval)
        self._lock = asyncio.Lock()
        self._last = 0.0

    async def __aenter__(self):
        await self._sem.acquire()
        if self._min_interval > 0:
            async with self._lock:
                loop = asyncio.get_event_loop()
                wait = self._min_interval - (loop.time() - self._last)
                if wait > 0:
                    await asyncio.sleep(wait)
                self._last = loop.time()
        return self

    async def __aexit__(self, *exc):
        self._sem.release()
