import threading

from bqclient.host.framework.logging import HostLogging

from bqclient.host.events import HostEvents
from bqclient.host.framework.events import bind_events
from bqclient.host.framework.ioc import Resolver
from bqclient.host.managers.bots_manager import BotsManager
from bqclient.host.managers.available_connections_manager import AvailableConnectionsManager
from bqclient.host.managers.websocket_manager import WebsocketManager
from bqclient.host.managers.worker_manager import WorkerManager


@bind_events
class Host(object):
    def __init__(self,
                 resolver: Resolver,
                 websocket_manager: WebsocketManager,
                 bots_manager: BotsManager,
                 worker_manager: WorkerManager,
                 available_connections_manager: AvailableConnectionsManager,
                 host_logging: HostLogging):
        self.resolver = resolver
        self.websocket_manager = websocket_manager
        self.worker_manager = worker_manager
        self.bots_manager = bots_manager
        self.available_connections_manager = available_connections_manager
        self.host_logger = host_logging.get_logger('Host')

        self._stop_event = threading.Event()

    def run(self):
        self.host_logger.info("Starting host run method")
        HostEvents.Startup().fire()

        self.host_logger.info("Starting Websocket Manager")
        self.websocket_manager.start()
        self.host_logger.info("Starting Bots Manager")
        self.bots_manager.start()
        self.host_logger.info("Starting Available Connections Manager")
        self.available_connections_manager.start()

        self._stop_event.wait()
        self.host_logger.info("Host told to shutdown")

        HostEvents.Shutdown().fire()
        self.host_logger.info("Finishing host run method")

    def stop(self):
        self._stop_event.set()
