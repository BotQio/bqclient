import click

import sentry_sdk
from appdirs import AppDirs

from bqclient.commands.run import RunCommand
from bqclient.commands.server import ServerCommand
from bqclient.host.framework.ioc import Resolver

sentry_sdk.init("https://ea5a7f74eda741ec8c84615d8b257736@sentry.io/1469260")


@click.group()
def main():
    resolver = Resolver.get()

    app_dirs = AppDirs(appname='BQClient')
    resolver.instance(app_dirs)


main.add_command(RunCommand())
main.add_command(ServerCommand())

if __name__ == '__main__':
    main()
