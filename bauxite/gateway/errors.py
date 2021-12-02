from bauxite.error import BauxiteError


class GatewayReconnect(BauxiteError):
    pass


class GatewayCriticalError(BauxiteError):
    def __init__(self, code: int) -> None:
        self.code = code

        super().__init__(f"Gateway disconnected with close code {code}")
