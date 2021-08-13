import click

from bqclient.host.configurations import HostConfiguration
from bqclient.host.framework.ioc import Resolver


class ServerCommand(click.Command):
    def __init__(self):
        super().__init__("server", params=[
            click.Argument(["server"])
        ])

    def invoke(self, ctx: click.Context):
        server_url = ctx.params['server']

        resolver = Resolver.get()

        host_config = resolver(HostConfiguration)
        host_config["server"] = server_url
