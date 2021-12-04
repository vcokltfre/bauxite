# Gateway Connections

---

## `GatewayClient`

```py
class GatewayClient:
    http: HTTPClient
    intents: int
    shard_count: Optional[int] = None
    shard_ids: Optional[list[int]] = None
    start_limiter: Optional[Type[GatewayRateLimiter]] = None
    status_hooks: Optional[list[ShardStatusHook]] = None
    callbacks: Optional[list[DispatchCallback]] = None
```

### Parameters

- `http` (`HTTPClient`) - The HTTP client to use for requests.
- `intents` (`int`) - The intents to use when connecting to the gateway.
- `shard_count` (optional `int`) - The number of shards to connect with.
- `shard_ids` (optional `list[int]`) - The IDs of the shards to connect with.
- `start_limiter` (optional `Type[GatewayRateLimiter]`) - The rate limiter class to use for ratelimiting gateway sends.
- `status_hooks` (optional `list[ShardStatusHook]`) - A list of status hooks to call when the shard status changes.
- `callbacks` (optional `list[DispatchCallback]`) - A list of callbacks to call when a, event is dispatched.

where `DispatchCallback = Callable[[Shard, EventDirection, dict], Awaitable[None]]`

### Methods

#### GatewayClient.spawn_shards

```py
async def spawn_shards()
```

###### Raises

- GatewayCriticalError

---
