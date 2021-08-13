import zeroconf

from bqclient.host.events import ServerDiscovery


class ServerDiscoveryManager(zeroconf.ServiceListener, object):
    def __init__(self):
        self._browser = None
        self._servers = set()

    def start(self):
        self._browser = zeroconf.ServiceBrowser(zeroconf.Zeroconf(), '_http._tcp.local.', self)

    def stop(self):
        if self._browser is not None:
            self._browser.cancel()

    def add_service(self, zc: zeroconf.Zeroconf, type_: str, name: str) -> None:
        info = zc.get_service_info(type_, name)

        if info is None:
            return

        if self._is_botqio_server(info):
            url = self._get_url(info)
            print(f"Added server {url}")

            if url not in self._servers:
                self._servers.add(url)
                ServerDiscovery.ServerDiscovered(url).fire()

    def remove_service(self, zc: zeroconf.Zeroconf, type_: str, name: str) -> None:
        pass

    def update_service(self, zc: zeroconf.Zeroconf, type_: str, name: str) -> None:
        pass

    @staticmethod
    def _is_botqio_server(info: zeroconf.ServiceInfo):
        return 'botqio' in info.properties or b'botqio' in info.properties

    @staticmethod
    def _get_url(info: zeroconf.ServiceInfo):
        if info.port == 80:
            url = "http://"
        elif info.port == 443:
            url = "https://"
        else:
            raise ValueError(f"Unknown port for BotQio zeroconf: {info.port}")

        url += info.server

        if url.endswith('.'):
            url = url[:-1]

        return url
