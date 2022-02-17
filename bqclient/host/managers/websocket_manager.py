from threading import Thread
from typing import Optional

from pysherplus.authentication import PysherAuthentication, AuthResult
from pysherplus.pusher import Pusher

from bqclient.host.api.commands.info import Info
from bqclient.host.api.rest import RestApi
from bqclient.host.framework.ioc import Resolver
from bqclient.host.framework.logging import HostLogging


class RestApiAuthentication(PysherAuthentication):
    def __init__(self,
                 url: str,
                 rest_api: RestApi):
        self._url = url
        self._rest_api = rest_api

    def auth_token(self, socket_id: str, channel_name: str) -> Optional[AuthResult]:
        response = self._rest_api.post(
            self._url,
            data={
                'socket_id': socket_id,
                'channel_name': channel_name
            }
        )

        if not response.ok:
            return None

        response_json = response.json()

        return AuthResult(
            token=response_json['auth'],
            user_data=response_json['channel_data'] if 'channel_data' in response_json else None
        )


class WebsocketManager(object):
    def __init__(self,
                 resolver: Resolver,
                 logging: HostLogging):
        self._resolver = resolver
        self._logger = logging.get_logger("WebsocketManager")
        self._thread = Thread(target=self._run)

    def start(self):
        self._thread.start()

    def _run(self):
        info: Info = self._resolver(Info)

        info_result = info()
        ws_url = info_result['websocket']['url']
        auth_url = info_result['websocket']['auth']

        if ws_url is None:
            self._logger.info("Websocket URL was not found")
            return

        if auth_url is None:
            self._logger.info("Websocket auth URL was not found")
            return

        rest_api: RestApi = self._resolver(RestApi)
        authenticator = RestApiAuthentication(auth_url, rest_api)
        pusher: Pusher = Pusher(ws_url, authenticator=authenticator)
        self._resolver.instance(pusher)

        self._logger.info(f"Connecting to websocket {ws_url} using auth url {auth_url}")
        pusher.connect()
