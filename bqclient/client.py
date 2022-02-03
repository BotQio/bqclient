from bqclient.host.workers.bot_worker import BotWorker
from bqclient.host import on
from bqclient.host.events import HostEvents, AuthFlowEvents
from bqclient.host.events import BotEvents
from bqclient.host.framework.events import bind_events
from bqclient.host.framework.ioc import Resolver
from bqclient.host.framework.logging import HostLogging


@bind_events
class BQClient(object):
    def __init__(self,
                 resolver: Resolver,
                 host_logging: HostLogging):
        self.resolver = resolver
        self.log = host_logging.get_logger('BQClient')
        self._workers = {}

    @on(AuthFlowEvents.HostRequestMade)
    def _host_request_made(self, event: AuthFlowEvents.HostRequestMade):
        print("Please go here in a web browser to claim this host!")
        print(event.host_request.url)

    @on(HostEvents.Startup)
    def _start(self):
        print("Host startup!")
        self.log.info("Host startup!")

    @on(HostEvents.Shutdown)
    def _shutdown(self):
        self.log.info("Host shutdown!")

    @on(BotEvents.BotAdded)
    def _bot_added(self, event: BotEvents.BotAdded):
        self.log.info(f"Bot added: {event.bot.name}")

    @on(BotEvents.BotRemoved)
    def _bot_removed(self, event):
        self.log.info("Bot removed! :(")
