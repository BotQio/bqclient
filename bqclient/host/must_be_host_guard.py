import time

from bqclient.host.api.commands.convert_request_to_host import ConvertRequestToHost
from bqclient.host.api.commands.refresh_access_token import RefreshAccessToken
from bqclient.host.api.commands.create_host_request import CreateHostRequest
from bqclient.host.api.commands.get_host_request import GetHostRequest
from bqclient.host.api.server import Server
from bqclient.host.configurations import HostConfiguration
from bqclient.host.events import ServerDiscovery
from bqclient.host.framework.ioc import Resolver
from bqclient.host.framework.events import on, bind_events
from bqclient.host.managers.server_discovery_manager import ServerDiscoveryManager


@bind_events
class MustBeHostGuard(object):
    def __init__(self,
                 resolver: Resolver,
                 config: HostConfiguration,
                 server_discovery_manager: ServerDiscoveryManager):
        self._resolver = resolver
        self.config = config
        self._loop_wait = 10
        self._server_discovery_manager = server_discovery_manager

    def __call__(self):
        if "server" in self.config:
            server_url = self.config["server"]
            server = self._resolver(Server, url=server_url)

            if server.access_token is None:
                if server.request_id is None:
                    create_host_request: CreateHostRequest = self._resolver(CreateHostRequest, server)

                    create_host_request()
            else:
                self._resolver.instance(server)

                host_refresh: RefreshAccessToken = self._resolver(RefreshAccessToken)

                host_refresh()

                return
        else:
            self._server_discovery_manager.start()

        while True:
            for server_url in self.config["servers"].keys():
                server = self._resolver(Server, url=server_url)

                # If we don't have a request id, there's nothing to look up
                if server.request_id is None:
                    continue

                get_host_request: GetHostRequest = self._resolver(GetHostRequest, server)
                response = get_host_request()

                if response["status"] == "claimed":
                    convert_to_host_request: ConvertRequestToHost = self._resolver(ConvertRequestToHost, server)
                    convert_to_host_request()
                    self._resolver.instance(server)
                    self.config["server"] = server_url

                    self._server_discovery_manager.stop()

                    return
                elif response["status"] == "expired":
                    # Try again with a new request id
                    del server.request_id

                    create_host_request: CreateHostRequest = self._resolver(CreateHostRequest, server)

                    create_host_request()

            time.sleep(self._loop_wait)

    @on(ServerDiscovery.ServerDiscovered)
    def _server_discovered(self, event: ServerDiscovery.ServerDiscovered):
        server = self._resolver(Server, url=event.url)

        if server.request_id is not None:
            return

        create_host_request: CreateHostRequest = self._resolver(CreateHostRequest, server)

        create_host_request()
