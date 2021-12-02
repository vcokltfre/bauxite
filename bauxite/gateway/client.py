from __future__ import annotations

from asyncio import Task, create_task, sleep
from typing import Awaitable, Callable, Optional, Type

from bauxite.http import HTTPClient, Route

from .enums import EventDirection
from .errors import GatewayCriticalError
from .ratelimiting import GatewayRateLimiter, LocalGatewayRateLimiter
from .shard import Shard, ShardStatusHook

DispatchCallback = Callable[[Shard, EventDirection, dict], Awaitable[None]]


class GatewayClient:
    def __init__(
        self,
        http: HTTPClient,
        intents: int,
        shard_count: Optional[int] = None,
        shard_ids: Optional[list[int]] = None,
        start_limiter: Optional[Type[GatewayRateLimiter]] = None,
        status_hooks: Optional[list[ShardStatusHook]] = None,
        callbacks: Optional[list[DispatchCallback]] = None,
    ) -> None:
        self._http = http

        self._intents = intents

        self._shard_count = shard_count
        self._shard_ids = shard_ids
        self._shard_hooks = status_hooks or []

        self._dispatch_callbacks = callbacks or []

        self._shards: dict[int, Shard] = {}
        self._tasks: dict[int, Task] = {}

        self._gateway: Optional[dict] = None

        self._limiter_class: Type[GatewayRateLimiter] = (
            start_limiter or LocalGatewayRateLimiter
        )
        self._panic: Optional[int] = None

    async def spawn_shards(self) -> None:
        if self._shard_count and not self._shard_ids:
            self._shard_ids = list(range(self._shard_count))

        self._gateway = gateway = await (
            await self._http.request(Route("GET", "/gateway/bot"))
        ).json()

        if self._shard_count:
            assert self._shard_ids

            for id in self._shard_ids:
                self._shards[id] = Shard(
                    id,
                    self._shard_count,
                    self._http._token,
                    self._intents,
                    self._dispatch,
                    self._shard_hooks,
                )
        else:
            for id in range(gateway["shards"]):
                self._shards[id] = Shard(
                    id,
                    gateway["shards"],
                    self._http._token,
                    self._intents,
                    self._dispatch,
                    self._shard_hooks,
                )

        await self._start_shards()

    async def _start_shards(self) -> None:
        assert self._gateway, "Client gateway is not set while starting shards."

        limiter = self._limiter_class(
            self._gateway["session_start_limit"]["max_concurrency"], 5
        )

        for shard in self._shards.values():
            if self._panic is not None:
                raise GatewayCriticalError(self._panic)

            await limiter.wait()

            self._tasks[shard.id] = create_task(self._run_shard(shard))

        while True:
            await sleep(1)

    async def _run_shard(self, shard: Shard) -> None:
        assert (
            self._gateway
        ), f"Client gateway is not set while running shard {shard.id}."

        try:
            await shard.connect(self._http._session, self._gateway["url"])
        except GatewayCriticalError:
            self._panic = True

    async def _dispatch(
        self, shard: Shard, direction: EventDirection, data: dict
    ) -> None:
        for callback in self._dispatch_callbacks:
            await callback(shard, direction, data)

    def get_shard(self, id: int) -> Shard:
        if id not in self._shards:
            raise ValueError(f"Shard of id {id} does not exist.")

        return self._shards[id]
