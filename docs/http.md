# HTTP Handling

---

## `HTTPClient`

```py
class HTTPClient:
    token: str
    api_url: Optional[str] = None
    user_agent: Optional[str] = None
    proxy_url: Optional[str] = None
    proxy_auth: Optional[BasicAuth] = None
    ratelimiter: Optional[RateLimiter] = None
    on_success: Optional[set[Callback]] = None
    on_error: Optional[set[Callback]] = None
    on_ratelimit: Optional[set[Callback]] = None
```

###### Parameters

- `token` (`str`) - The token to use when making requests.
- `api_url` (optional `str`) - The base API URL to use for requests.
- `user_agent` (optional `str`) - A custom user agent to use when making requests.
- `proxy_url` (optional `str`) - The URL of a proxy to use when making requests.
- `proxy_auth` (optional `BasicAuth`) - The authentication to use when making requests through the proxy.
- `ratelimiter` (optional `RateLimiter`) - The ratelimiter to use for ratelimiting requests.
- `on_success` (optional `set[Callback]`) - A set of callbacks to be called upon successful requests.
- `on_error` (optional `set[Callback]`) - A set of callbacks to be called upon unsuccessful requests.
- `on_ratelimit` (optional `set[Callback]`) - A set of callbacks to be called upon ratelimited requests, or requests that drain the ratelimit bucket for a route.

where `Callback = Callable[[ClientResponse, Route], Awaitable[None]]`

### Methods

#### `HTTPClient.request`

```py
async def request(
    route: Route,
    qparams: Optional[dict[str, Union[str, int]]] = None,
    reason: Optional[str] = None,
    files: Optional[Sequence[File]] = None,
    json: Optional[Any] = Unset,
    max_attempts: int = 3,
)
```

###### Returns

`ClientResponse` - The response from the request.

###### Parameters

- `route` (`Route`) - The route to request.
- `qparams` (`dict[str: Any]`) - A dictionary of query parameters to add to the request.
- `reason` (optional `str`) - A reason for the audit log. Defaults to None
- `files` (optional `Sequence[File]`) - A sequence of files to upload.
- `json` (optional `Any`) - A JSON object to send as the request body.
- `max_attempts` (`int`) - The maximum number of attempts to make before failing.

###### Raises

- HTTPError
    - BadRequest
        - Unauthorized
        - Forbidden
        - NotFound
        - MethodNotAllowed
        - UnprocessableEntity
        - TooManyRequests
    - ServerError
        - BadGateway
        - ServiceUnavailable
        - GatewayTimeout

---

## `File`

```py
class File:
    fp: Union[IOBase, PathLike, str]
    filename: Optional[str] = None
    spoiler: bool = False
```

#### Parameters

- `fp` (`Union[IOBase, PathLike, str]`) - The file path or a file object.
- `filename` (optional `str`) - The filename to use for the file. Defaults to the filename of the file. (This must be provided if `fp` is an `IOBase` object.)
- `spoiler` (`bool`) - Whether or not the file is a spoiler. Defaults to `False`.

---

## `Route`

```py
class Route:
    method: str
    path: str
    **params
```

###### Parameters

- `method` (`str`) - The HTTP method to use.
- `path` (`str`) - The path to use (including the initial `/`).
- `params` (kwargs dict of `str: Any`) - Parameters to format the path with.

###### Attributes

- `guild_id` (optional `int`) - The of the guild in the route.
- `channel_id` (optional `int`) - The of the channel in the route.
- `webhook_id` (optional `int`) - The of the webhook in the route.
- `webhook_token` (optional `str`) - The token of the webhook in the route.
- `method` (`str`) - The HTTP method being used.
- `path` (`str`) - The formatted route path.
- `bucket` (`str`) - The ratelimiting bucket for the route.
