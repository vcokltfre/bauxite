# Bauxite

Bauxite is a robust, low-level connector for the Discord API.

## What is Bauxite for?

Bauxite is made for two main purposes:

- Creating higher-level API wrappers and frameworks
- Creating things that need high levels of control and low-level access to the Discord API

## Examples

### Basic HTTP Example

```py
from asyncio import run

from bauxite import HTTPClient, Route


async def main() -> None:
    client = HTTPClient("your_bot_token")

    await client.request(
        Route("POST", "/channels/{channel_id}/messages", channel_id=1234),
        json={
            "content": "Hello, world!",
        },
    )

    await client.close()

run(main())
```

### Basic Gateway Example

```py
from asyncio import run

from bauxite import GatewayClient, HTTPClient


async def callback(shard, direction, data) -> None:
    print(f"{shard} [{direction}]: {data['op'] or data['t']}")

async def main() -> None:
    client = HTTPClient("your_bot_token")
    gateway = GatewayClient(client, 32767, callbacks=[callback])

    await gateway.spawn_shards()

run(main())
```
