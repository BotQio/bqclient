from bqclient.host.api.botqio_api import BotQioApi
from bqclient.host.api.server import Server
from bqclient.host.configurations import HostConfiguration


class RefreshAccessToken(object):
    def __init__(self,
                 config: HostConfiguration,
                 api: BotQioApi,
                 server: Server):
        self.config = config
        self.api = api
        self._server = server

    def __call__(self):
        response = self.api.command("RefreshAccessToken")

        self._server.access_token = response["access_token"]
