import queue
import time
from logging import Logger
from queue import Queue
from threading import Event, Thread
from typing import Optional

from bqclient.host.api.commands.finish_job import FinishJob
from bqclient.host.api.commands.start_job import StartJob
from bqclient.host.api.commands.update_job_progress import UpdateJobProgress
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
        self._current_job: Optional[Job] = None

        self._logger: Logger = host_logging.get_logger(f"BotWorker:{self._bot.id}")
        self._event_loop_stop: Event = Event()
        self._input_queue: Queue = Queue()

        self._current_driver_config = self._bot.driver
        self._current_driver: Optional[DriverInterface] = None
        self._connection_attempted = False

        self._last_progress_time = 0
        self._last_progress = 0

        self._thread = Thread(target=self.event_loop, daemon=True)
        self._thread.start()

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
            self._logger.info(f"Command: {command}")
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

        self._current_driver.job_started_callback = self._driver_handle_job_started
        self._current_driver.job_finished_callback = self._driver_handle_job_finished
        self._current_driver.job_progress_callback = self._driver_handle_job_progress

        self._current_driver.connect()
        self._connection_attempted = True

    def _handle_disconnection(self):
        if self._current_driver is not None:
            self._current_driver.disconnect()

        self._current_driver = None
        self._connection_attempted = False

    def _handle_run_job_command(self, command: RunJobCommand):
        self._logger.info(f"Running job {command.job.id} ({command.job.name})")
        self._current_job = command.job

        downloader: Downloader = self._resolver(Downloader)
        local_path = downloader.download(command.job.file)

        start_job = self._resolver(StartJob)
        start_job(command.job.id)

        self._current_driver.start(local_path)

        command.completed.set()

    def _driver_handle_job_started(self):
        self._last_progress = 0
        self._last_progress_time = 0

    def _driver_handle_job_progress(self, progress: float):
        current_time = time.time()

        should_update = (progress - self._last_progress) > 0.5
        should_update |= (current_time - self._last_progress_time) > 5

        if not should_update:
            return

        self._last_progress_time = current_time
        self._last_progress = progress

        update_job_progress: UpdateJobProgress = self._resolver(UpdateJobProgress)
        update_job_progress(self._current_job.id, progress)

    def _driver_handle_job_finished(self):
        self._logger.info(f"Job {self._current_job.id} finished.")
        finish_job = self._resolver(FinishJob)
        finish_job(self._current_job.id)
