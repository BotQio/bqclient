from unittest.mock import Mock

from bqclient.host.api.botqio_api import BotQioApi
from bqclient.host.api.commands.create_host_request import CreateHostRequest
from bqclient.host.api.server import Server
from bqclient.host.events import AuthFlowEvents


class TestCreateHostRequest(object):
    def test_host_request_sets_host_request_id(self, resolver, fakes_events):
        fakes_events.fake(AuthFlowEvents.HostRequestMade)

        server = resolver(Server, url="https://server/")
        resolver.instance(server)

        api = Mock(BotQioApi)
        api.command.return_value = {
                "id": 1,
                "status": "requested"
            }
        resolver.instance(api)

        make_host_request = resolver(CreateHostRequest)

        make_host_request()

        api.command.assert_called_once_with("CreateHostRequest")

        assert server.request_id == 1
        assert fakes_events.fired(AuthFlowEvents.HostRequestMade).once()

        event: AuthFlowEvents.HostRequestMade = fakes_events.fired(AuthFlowEvents.HostRequestMade).event
        assert event.host_request.id == 1
        assert event.host_request.status == "requested"
        assert event.host_request.server == server.url
        assert event.host_request.url == f"{server.url}/hosts/requests/1"
