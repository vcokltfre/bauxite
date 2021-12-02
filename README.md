# Bauxite

Bauxite is a robus, low-level connector for the Discord API.

## What is Bauxite for?

Bauxite is made for two main purposes:

- Creating higher-level API wrappers and frameworks
- Creating things that need high levels of control and low-level access to the Discord API

## Basic HTTP Example

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
