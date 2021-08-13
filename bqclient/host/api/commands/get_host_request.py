from bqclient.host.api.botqio_api import BotQioApi
from bqclient.host.api.server import Server


class GetHostRequest(object):
    def __init__(self,
                 server: Server,
                 api: BotQioApi):
        self._server = server
        self.api = api

    def __call__(self):
        return self.api.command("GetHostRequest", {
            "id": self._server.request_id
        })
