from __future__ import annotations

from asyncio import create_task, sleep
from collections import defaultdict
from dataclasses import dataclass
from json import dumps
from typing import Any, Awaitable, Callable, Mapping, Optional, Sequence, Type, Union

from aiohttp import BasicAuth, ClientResponse, ClientSession, FormData

from bauxite.constants import API_URL, VERSION

from .errors import (
    BadGateway,
    BadRequest,
    Forbidden,
    GatewayTimeout,
    HTTPError,
    MethodNotAllowed,
    NotFound,
    ServerError,
    ServiceUnavailable,
    TooManyRequests,
    Unauthorized,
    UnprocessableEntity,
)
from .file import File
from .ratelimiting import LocalRateLimiter, RateLimiter
from .route import Route

Callback = Callable[[ClientResponse, Route], Awaitable[None]]
Unset = object()


@dataclass
class _RequestContext:
    route: Route
    headers: dict[str, str]
    params: dict[str, Any]
    files: Sequence[File]
    json: Any


@dataclass
class _ResponseContext:
    route: Route
    response: ClientResponse
    successful: bool


class HTTPClient:
    _status_codes: Mapping[int, Type[HTTPError]] = defaultdict(
        lambda: HTTPError,
        {
            400: BadRequest,
            401: Unauthorized,
            403: Forbidden,
            404: NotFound,
            405: MethodNotAllowed,
            422: UnprocessableEntity,
            429: TooManyRequests,
            500: ServerError,
            502: BadGateway,
            503: ServiceUnavailable,
            504: GatewayTimeout,
        },
    )

    def __init__(
        self,
        token: str,
        api_url: Optional[str] = None,
        user_agent: Optional[str] = None,
        proxy_url: Optional[str] = None,
        proxy_auth: Optional[BasicAuth] = None,
        ratelimiter: Optional[RateLimiter] = None,
        on_success: Optional[set[Callback]] = None,
        on_error: Optional[set[Callback]] = None,
        on_ratelimit: Optional[set[Callback]] = None,
    ) -> None:
        self._token = token.strip()
        self._api_url = api_url or API_URL
        self._user_agent = (
            user_agent
            or f"DiscordBot (https://github.com/vcokltfre/bauxite, {VERSION})"
        )
        self._proxy_url = proxy_url
        self._proxy_auth = proxy_auth
        self._ratelimiter = ratelimiter or LocalRateLimiter()

        self.__session: Optional[ClientSession] = None

        self._on_success = on_success or set()
        self._on_error = on_error or set()
        self._on_ratelimit = on_ratelimit or set()

    @property
    def _session(self) -> ClientSession:
        if self.__session and not self.__session.closed:
            return self.__session

        self.__session = ClientSession(
            headers={
                "Authorization": f"Bot {self._token}",
                "User-Agent": self._user_agent,
            }
        )

        return self.__session

    def _dispatch(self, listeners: set[Callback], ctx: _ResponseContext) -> None:
        for listener in listeners:
            create_task(listener(ctx.response, ctx.route))

    async def _request(
        self, ctx: _RequestContext, reset_files: int
    ) -> _ResponseContext:
        if ctx.files:
            data = FormData()

            for i, file in enumerate(ctx.files):
                file.reset(reset_files)

                data.add_field(f"file_{i}", file.fp, filename=file.filename)

            if ctx.json is not Unset:
                data.add_field(
                    "payload_json", dumps(ctx.json), content_type="application/json"
                )

            ctx.params["data"] = data
        elif ctx.json is not Unset:
            ctx.params["json"] = ctx.json

        lock = await self._ratelimiter.acquire(ctx.route.bucket)

        async with lock:
            response = await self._session.request(
                ctx.route.method,
                self._api_url + ctx.route.path,
                headers=ctx.headers,
                **ctx.params,
            )

            status = response.status
            headers = response.headers

            response_ctx = _ResponseContext(ctx.route, response, 200 <= status < 300)

            rl_reset_after = float(headers.get("X-RateLimit-Reset-After", 0))
            rl_bucket_remaining = int(headers.get("X-RateLimit-Remaining", 1))

            if response_ctx.successful:
                self._dispatch(self._on_success, response_ctx)
                if rl_bucket_remaining == 0:
                    self._dispatch(self._on_ratelimit, response_ctx)
                    await lock.release(rl_reset_after)
                else:
                    await lock.release(0)
                return response_ctx
            elif status == 429:
                self._dispatch(self._on_error, response_ctx)
                self._dispatch(self._on_ratelimit, response_ctx)
                if not headers.get("Via"):
                    raise TooManyRequests(response)

                json = await response.json()

                is_global = json.get("global", False)
                retry_after = json["retry_after"]

                if is_global:
                    await self._ratelimiter.lock_globally(retry_after)
                else:
                    await lock.release(retry_after)
            else:
                self._dispatch(self._on_error, response_ctx)
                raise self._status_codes[status](response)

            return response_ctx

    async def request(
        self,
        route: Route,
        qparams: Optional[dict[str, Union[str, int]]] = None,
        reason: Optional[str] = None,
        files: Optional[Sequence[File]] = None,
        json: Optional[Any] = Unset,
        max_attempts: int = 3,
    ) -> ClientResponse:
        headers = {}
        params = {}

        if qparams:
            params["params"] = qparams

        if reason:
            headers["X-Audit-Log-Reason"] = reason

        for attempt in range(max_attempts):
            ctx = _RequestContext(route, headers, params, files or (), json)
            resp = await self._request(ctx, attempt)

            if resp.successful:
                return resp.response

            if attempt == max_attempts - 1:
                raise self._status_codes[resp.response.status](resp.response)

            await sleep(1 + attempt * 2)

        raise Exception("Unreachable")

    async def close(self) -> None:
        if self.__session:
            await self.__session.close()
