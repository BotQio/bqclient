from bqclient.host.api.botqio_api import BotQioApi
from bqclient.host.api.server import Server
from bqclient.host.events import AuthFlowEvents
from bqclient.host.types import Host


class ConvertRequestToHost(object):
    def __init__(self,
                 server: Server,
                 api: BotQioApi):
        self._server = server
        self.api = api

    def __call__(self):
        request_id = self._server.request_id

        response = self.api.command("ConvertRequestToHost", {
            "id": request_id
        })

        self._server.access_token = response["access_token"]
        self._server.host_id = response["host"]["id"]
        self._server.host_name = response["host"]["name"]

        del self._server.request_id

        host = Host(
            id=response["host"]["id"],
            name=response["host"]["name"]
        )

        AuthFlowEvents.HostMade(host).fire()
