from unittest.mock import MagicMock, patch

from pysherplus.pusher import Pusher

from bqclient.host.api.commands.info import Info
from bqclient.host.api.rest import RestApi
from bqclient.host.managers.websocket_manager import WebsocketManager, RestApiAuthentication


class TestWebsocketManager(object):
    ws_url = 'ws://example.com/ws/app/BotQio/key'
    auth_url = 'http://example.com/broadcasting/auth'

    def test_websocket_manager_calls_info_command_to_setup_websocket(self, resolver):
        info = MagicMock(Info)
        resolver.instance(info)
        info.return_value = {
            'websocket': {
                'url': self.ws_url,
                'auth': self.auth_url,
            }
        }

        rest_api = MagicMock(RestApi)
        resolver.instance(rest_api)

        with patch('bqclient.host.managers.websocket_manager.Pusher') as pusher_class, \
                patch('bqclient.host.managers.websocket_manager.RestApiAuthentication') as auth_class:
            pusher_instance = MagicMock(Pusher)
            pusher_class.return_value = pusher_instance

            auth_instance = MagicMock(RestApiAuthentication)
            auth_class.return_value = auth_instance

            manager: WebsocketManager = resolver(WebsocketManager)

            manager.start()

            manager._thread.join(1)

            info.assert_called_once()

            auth_class.assert_called_once_with(self.auth_url, rest_api)

            pusher_class.assert_called_once_with(self.ws_url, authenticator=auth_instance)
            pusher_instance.connect.assert_called_once()

            assert resolver(Pusher) is pusher_instance
