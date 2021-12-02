from asyncio import Task, create_task, sleep
from random import randrange
from sys import platform
from time import time
from typing import Awaitable, Callable, Optional

from aiohttp import (
    ClientSession,
    ClientWebSocketResponse,
    WebSocketError,
    WSMessage,
    WSMsgType,
    WSServerHandshakeError,
)

from .enums import EventDirection, GatewayCloseCodes, GatewayOps, ShardStatus
from .errors import GatewayCriticalError, GatewayReconnect
from .ratelimiting import GatewayRateLimiter, LocalGatewayRateLimiter

CRITICAL = [
    GatewayCloseCodes.NOT_AUTHENTICATED,
    GatewayCloseCodes.AUTHENTICATION_FAILED,
    GatewayCloseCodes.INVALID_API_VERSION,
    GatewayCloseCodes.INVALID_INTENTS,
    GatewayCloseCodes.DISALLOWED_INTENTS,
]

NONCRITICAL = [
    GatewayCloseCodes.INVALID_SEQ,
    GatewayCloseCodes.RATE_LIMITED,
    GatewayCloseCodes.SESSION_TIMEOUT,
]

ShardStatusHook = Callable[["Shard", ShardStatus], Awaitable[None]]


class Shard:
    def __init__(
        self,
        shard_id: int,
        shard_count: int,
        token: str,
        intents: int,
        callback: Callable[["Shard", EventDirection, dict], Awaitable[None]],
        status_hooks: list[ShardStatusHook],
        ratelimiter: Optional[GatewayRateLimiter] = None,
    ) -> None:
        self.id = shard_id

        self._count = shard_count
        self._token = token
        self._intents = intents
        self._callback = callback
        self._hooks = status_hooks
        self._send_limiter = ratelimiter or LocalGatewayRateLimiter(120, 60)

        self._ws: Optional[ClientWebSocketResponse] = None
        self._hb: Optional[float] = None
        self._hb_interval: Optional[float] = None

        self._ack: Optional[bool] = None
        self._last_hb: Optional[float] = None
        self._last_ack: Optional[float] = None

        self._pacemaker: Optional[Task] = None

        self._session: Optional[str] = None
        self._seq: Optional[int] = None

    def __repr__(self) -> str:
        return f"<Shard id={self.id}>"

    @property
    def latency(self) -> Optional[float]:
        if self._last_hb and self._last_ack:
            return self._last_ack - self._last_hb
        return

    def _status_hook(self, status: ShardStatus):
        for hook in self._hooks:
            create_task(hook(self, status))

    async def _spawn_ws(self, session: ClientSession, url: str) -> None:
        self._ws = await session.ws_connect(url)

    async def _connect(self, session: ClientSession, url: str) -> None:
        self._status_hook(ShardStatus.CONNECTING)

        try:
            await self._spawn_ws(session, url)
        except (WebSocketError, WSServerHandshakeError) as e:
            return

        if self._session:
            await self._resume()

        try:
            await self._read()
        except GatewayReconnect:
            pass

    async def connect(self, session: ClientSession, url: str) -> None:
        backoff = 0.01

        while True:
            await sleep(backoff)
            try:
                await self._connect(session, url)
                backoff = 0.01
            except Exception as e:
                if backoff < 5:
                    backoff *= 2

    async def _close(self) -> None:
        self._hb = None

        if self._ws and not self._ws.closed:
            await self._ws.close()

        if self._pacemaker and not self._pacemaker.cancelled():
            self._pacemaker.cancel()

    async def _send(self, message: dict) -> None:
        await self._send_limiter.wait()
        await self._callback(self, EventDirection.OUTBOUND, message)

        try:
            await self._ws.send_json(message)  # type: ignore
        except OSError:
            await self._close()
        except Exception:
            await self._close()
            raise

    async def _identify(self) -> None:
        await self._send(
            {
                "op": GatewayOps.IDENTIFY,
                "d": {
                    "token": self._token,
                    "properties": {
                        "$os": platform,
                        "$browser": "Ablaze",
                        "$device": "Ablaze",
                    },
                    "intents": self._intents,
                    "shard": [self.id, self._count],
                },
            }
        )

    async def _resume(self) -> None:
        self._status_hook(ShardStatus.RESUMING)

        await self._send(
            {
                "op": GatewayOps.RESUME,
                "d": {
                    "token": self._token,
                    "session_id": self._session,
                    "seq": self._seq,
                },
            }
        )

    async def _dispatch(self, data: dict) -> None:
        await self._callback(self, EventDirection.INBOUND, data)

        op = data["op"]

        if op == GatewayOps.HELLO:
            self._pacemaker = create_task(
                self._start_pacemaker(data["d"]["heartbeat_interval"])
            )
            await self._identify()
        elif op == GatewayOps.ACK:
            self._last_ack = time()
            self._ack = True
        elif op == GatewayOps.RECONNECT:
            await self._close()
            raise GatewayReconnect()

    async def _handle_disconnect(self, code: int) -> None:
        """Handle the gateway disconnecting correctly."""

        self._status_hook(ShardStatus.ERRORED)

        if code in CRITICAL:
            raise GatewayCriticalError(code)

        if code in NONCRITICAL:
            self._session = None
            self._seq = None

        await self._close()

        raise GatewayReconnect()

    async def _read(self) -> None:
        self._status_hook(ShardStatus.CONNECTED)

        assert self._ws, "WebSocket is not spawned while _read() is called."

        async for message in self._ws:
            message: WSMessage

            if message.type == WSMsgType.TEXT:
                message_data = message.json()

                if s := message_data.get("s"):
                    self._seq = s

                await self._dispatch(message_data)

        assert self._ws and self._ws.close_code

        await self._handle_disconnect(self._ws.close_code)

    async def _start_pacemaker(self, delay: float) -> None:
        delay = delay / 1000

        await sleep(randrange(0, int(delay)))

        while True:
            if self._last_ack and time() - self._last_ack >= delay:
                return await self._close()

            await self._heartbeat()

            await sleep(delay)

    async def _heartbeat(self) -> None:
        self._last_hb = time()

        await self._send({"op": GatewayOps.HEARTBEAT, "d": self._seq})
