from asyncio import Semaphore, create_task, sleep
from typing import Protocol


class GatewayRateLimiter(Protocol):
    per: int

    def __init__(self, rate: int, per: int) -> None:
        ...

    async def wait(self) -> None:
        ...


class LocalGatewayRateLimiter:
    def __init__(self, rate: int, per: int) -> None:
        self.per = per

        self._lock = Semaphore(rate)

    async def _release(self, after: float) -> None:
        await sleep(after)

        self._lock.release()

    async def wait(self) -> None:
        await self._lock.acquire()

        create_task(self._release(self.per))
