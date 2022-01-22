import queue
from queue import Queue
from threading import Event
from typing import Optional

from bqclient.host.api.commands.start_job import StartJob
from bqclient.host.downloader import Downloader
from bqclient.host.drivers.driver_factory import DriverFactory
from bqclient.host.drivers.driver_interface import DriverInterface
from bqclient.host.framework.events import bind_events
from bqclient.host.framework.ioc import Resolver
from bqclient.host.framework.logging import HostLogging
from bqclient.host.models import Bot, Job


class WorkerCommand(object):
    def __init__(self):
        self._completed: Event = Event()

    @property
    def completed(self) -> Event():
        return self._completed


class DriverUpdatedCommand(WorkerCommand):
    def __init__(self, driver_config):
        super().__init__()
        self.driver_config = driver_config


# Nop = No operation
# Useful for tests to make sure the thread has gone through the event loop at least once for assertions
class NopCommand(WorkerCommand):
    pass


class RunJobCommand(WorkerCommand):
    def __init__(self, job: Job):
        super().__init__()
        self.job = job


class ShutdownCommand(WorkerCommand):
    pass


@bind_events
class BotWorker(object):
    def __init__(self,
                 bot: Bot,
                 resolver: Resolver,
                 host_logging: HostLogging):
        self._resolver = resolver
        self._bot = bot
        self._logging = host_logging
        self._event_loop_stop: Event = Event()
        self._input_queue: Queue = Queue()

        self._current_driver_config = self._bot.driver
        self._current_driver: Optional[DriverInterface] = None
        self._connection_attempted = False

    @property
    def input_queue(self) -> Queue:
        return self._input_queue

    def event_loop(self):
        self._handle_connection()  # Initial connection in the likely event the bot already has a driver

        while not self._event_loop_stop.is_set():
            self._handle_command()  # Must go last for NopCommand's guarantees for testing

    def _handle_command(self):
        try:
            command: WorkerCommand = self._input_queue.get(timeout=0.1)
        except queue.Empty:
            return

        if isinstance(command, DriverUpdatedCommand):
            self._handle_driver_update(command)
        if isinstance(command, NopCommand):
            command.completed.set()
        if isinstance(command, RunJobCommand):
            self._handle_run_job_command(command)
        if isinstance(command, ShutdownCommand):
            self._event_loop_stop.set()
            command.completed.set()

    def _handle_driver_update(self, command):
        self._handle_disconnection()
        self._current_driver_config = command.driver_config
        self._handle_connection()
        command.completed.set()

    def _handle_connection(self):
        if self._current_driver_config is None:
            return

        if self._current_driver is not None:
            return

        if self._connection_attempted:
            return

        driver_factory: DriverFactory = self._resolver(DriverFactory)
        self._current_driver: DriverInterface = driver_factory.get(self._current_driver_config)

        self._current_driver.connect()
        self._connection_attempted = True

    def _handle_disconnection(self):
        if self._current_driver is not None:
            self._current_driver.disconnect()

        self._current_driver = None
        self._connection_attempted = False

    def _handle_run_job_command(self, command: RunJobCommand):
        downloader: Downloader = self._resolver(Downloader)
        local_path = downloader.download(command.job.file)

        start_job = self._resolver(StartJob)
        start_job(command.job.id)

        self._current_driver.start(local_path)

        command.completed.set()