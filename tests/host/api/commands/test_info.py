from unittest.mock import Mock

from bqclient.host.api.botqio_api import BotQioApi
from bqclient.host.api.commands.info import Info
from bqclient.host.api.server import Server


class TestInfo(object):
    def test_info_command_calls_api(self, resolver):
        server = resolver(Server, url="https://server/")
        resolver.instance(server)

        api = Mock(BotQioApi)
        data = {
            'websocket': {
                'url': 'ws://example.com/ws/app/BotQio/key',
                'auth': 'http://example.com/broadcasting/auth',
            }
        }
        api.command.return_value = data
        resolver.instance(api)

        info = resolver(Info)

        result = info()

        api.command.assert_called_once_with("Info")

        assert result == data
