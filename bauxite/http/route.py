from typing import Literal, Optional

HTTPMethod = Literal["GET", "HEAD", "POST", "DELETE", "PUT", "PATCH"]


class Route:
    def __init__(self, method: HTTPMethod, path: str, **params) -> None:
        self.guild_id: Optional[int] = params.get("guild_id")
        self.channel_id: Optional[int] = params.get("channel_id")
        self.webhook_id: Optional[int] = params.get("webhook_id")
        self.webhook_token: Optional[str] = params.get("webhook_token")

        self.method = method
        self.path = path.format(**params)

        self._webhook_bucket: Optional[str] = None
        if self.webhook_id:
            self._webhook_bucket = f"{self.webhook_id}:{self.webhook_token}"

        self.bucket = (
            f"{self.path}-{self.guild_id}:{self.channel_id}:{self._webhook_bucket}"
        )
