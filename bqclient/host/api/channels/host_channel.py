import json
from typing import Optional, Any, Dict, List, Callable

from pysherplus.channel import Channel, EventCallback
from pysherplus.pusher import Pusher
from sentry_sdk import capture_exception

from bqclient.host.api.server import Server
from bqclient.host.framework.ioc import Resolver, singleton
from bqclient.host.framework.logging import HostLogging


@singleton
class HostSocketChannel(object):
    def __init__(self,
                 server: Server,
                 resolver: Resolver,
                 logging: HostLogging):
        self._resolver = resolver
        self._server = server
        self._logger = logging.get_logger('HostSocketChannel')
        self._host_channel_name = f'private-hosts.{self._server.host_id}'

        self._client: Optional[Pusher] = None
        self._host_channel: Optional[Channel] = None

        self._listeners: Dict[str, List[EventCallback]] = {}

        resolver.on_bind(Pusher, self._on_pusher_available)

    def register(self, event_name: str, callback: EventCallback):
        self._listeners.setdefault(event_name, []).append(callback)

    def unregister(self, event_name: str, callback: EventCallback):
        listeners = self._listeners.setdefault(event_name, [])
        if callback in listeners:
            listeners.remove(callback)

    def _on_pusher_available(self):
        self._client: Pusher = self._resolver(Pusher)
        self._host_channel = self._client[self._host_channel_name]
        self._host_channel['*'].register(self._event)
        self._logger.info("Pusher instance is now available")

    @property
    def subscribed(self) -> bool:
        if self._host_channel is None:
            return False

        return self._host_channel.subscribed

    def _event(self, event_name: str, data: Any):
        if isinstance(data, str):
            data = json.loads(data)

        app_events_prefix = 'App\\Events\\'
        event_name_sans_prefix = event_name.removeprefix(app_events_prefix)

        # This allows subscribers to 'App\Events\Name' and 'Name'.
        # It will call the callback with their preferred format.
        for name in {event_name, event_name_sans_prefix}:
            if name not in self._listeners:
                continue

            listener: EventCallback
            for listener in self._listeners[name]:
                try:
                    listener(name, data)
                except Exception as ex:
                    capture_exception(ex)
