import asyncio
import threading
import typing as t


class AsyncUtil:
    is_async_code: t.ClassVar = True


class Util:
    is_async_code: t.ClassVar = False


class AsyncLock:
    """Async counterpart of :class:`Lock`, used to guard lazy connection setup.

    The async ``Database`` singleton is instantiated at import time - before any
    event loop is running - and may be used from more than one loop over its
    lifetime (e.g. successive ``asyncio.run`` calls in a test suite). A plain
    ``asyncio.Lock`` created up-front would bind to the wrong loop, so the
    underlying lock is created lazily, once per running loop.
    """

    def __init__(self) -> None:
        self._locks: dict[asyncio.AbstractEventLoop, asyncio.Lock] = {}

    def _get_lock(self) -> asyncio.Lock:
        loop = asyncio.get_running_loop()
        lock = self._locks.get(loop)
        if lock is None:
            lock = asyncio.Lock()
            self._locks[loop] = lock
        return lock

    async def __aenter__(self) -> "AsyncLock":
        await self._get_lock().acquire()
        return self

    async def __aexit__(self, *exc_info: t.Any) -> None:
        self._get_lock().release()


class Lock:
    """Sync counterpart of :class:`AsyncLock`, wrapping a ``threading.Lock``."""

    def __init__(self) -> None:
        self._lock = threading.Lock()

    def __enter__(self) -> "Lock":
        self._lock.acquire()
        return self

    def __exit__(self, *exc_info: t.Any) -> None:
        self._lock.release()
