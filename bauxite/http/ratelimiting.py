from __future__ import annotations

from asyncio import Event, Lock, create_task, sleep
from typing import Protocol


class BucketLock(Protocol):
    async def __aenter__(self) -> "BucketLock":
        ...

    async def __aexit__(self, *args, **kwargs) -> None:
        ...

    async def release(self, after: float = 0) -> None:
        ...


class RateLimiter(Protocol):
    async def acquire(self, bucket: str) -> BucketLock:
        ...

    async def lock_globally(self, release_after: float) -> None:
        ...


class LocalBucketLock:
    def __init__(self) -> None:
        self._lock = Lock()

    async def _release(self, after: float) -> None:
        await sleep(after)
        self._lock.release()

    async def __aenter__(self) -> "LocalBucketLock":
        await self._lock.acquire()
        return self

    async def __aexit__(self, *args, **kwargs) -> None:
        pass

    async def release(self, after: float = 0) -> None:
        create_task(self._release(after))


class LocalRateLimiter:
    def __init__(self) -> None:
        self.buckets: dict[str, BucketLock] = {}

        self._global = Event()
        self._global.set()

    async def _lock_global(self, release_after: float) -> None:
        self._global.clear()
        await sleep(release_after)
        self._global.set()

    async def acquire(self, bucket: str) -> BucketLock:
        if not (lock := self.buckets.get(bucket)):
            lock = LocalBucketLock()
            self.buckets[bucket] = lock

        await self._global.wait()
        return lock

    async def lock_globally(self, release_after: float) -> None:
        create_task(self._lock_global(release_after))
