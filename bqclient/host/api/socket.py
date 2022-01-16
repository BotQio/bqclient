from typing import Optional

from pysherplus.pusher import Pusher

from bqclient.host.framework.ioc import singleton, Resolver


# @singleton
class WebSocketApi(object):
    def __init__(self,
                 resolver: Resolver):
        self._resolver = resolver
        self._client: Optional[Pusher] = None

        #resolver.on_bind(Pusher, self._on_pusher_available)

    def _on_pusher_available(self):
        self._client = self._resolver(Pusher)

    @property
    def client(self) -> Optional[Pusher]:
        return self._client

    @property
    def connected(self):
        if self._client is None:
            return False
        return self._client.connected
