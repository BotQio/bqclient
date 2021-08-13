import signal
from threading import Thread

import click

from bqclient.client import BQClient
from bqclient.host import Host
from bqclient.host.framework.ioc import Resolver
from bqclient.host.must_be_host_guard import MustBeHostGuard


class RunCommand(click.Command):
    def __init__(self):
        super().__init__("run")

    def invoke(self, ctx: click.Context):
        resolver = Resolver.get()

        # This ensures that the events of BQClient are registered
        client = resolver(BQClient)

        must_be_host_guard: MustBeHostGuard = resolver(MustBeHostGuard)

        must_be_host_guard()

        host: Host = resolver(Host)

        thread = Thread(target=host.run)

        def stop_host(signum, frame):
            host.stop()

        signal.signal(signal.SIGINT, stop_host)
        signal.signal(signal.SIGTERM, stop_host)

        thread.start()
        thread.join()
