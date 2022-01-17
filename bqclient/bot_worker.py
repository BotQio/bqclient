import time
from threading import Thread, Event
from typing import Optional

from bqclient.host import on
from bqclient.host.api.botqio_api import ErrorResponse
from bqclient.host.api.commands.bot_error import BotError
from bqclient.host.api.commands.finish_job import FinishJob
from bqclient.host.api.commands.get_a_job import GetAJob
from bqclient.host.api.commands.start_job import StartJob
from bqclient.host.api.commands.update_job_progress import UpdateJobProgress
from bqclient.host.api.errors import Errors
from bqclient.host.downloader import Downloader
from bqclient.host.drivers.driver_factory import DriverFactory
from bqclient.host.events import JobEvents, BotEvents
from bqclient.host.framework.events import bind_events
from bqclient.host.framework.ioc import Resolver
from bqclient.host.framework.logging import HostLogging
from bqclient.host.models import Bot, Job


@bind_events
class BotWorker(object):
    def __init__(self,
                 bot: Bot,
                 resolver: Resolver,
                 host_logging: HostLogging):
        self.bot = bot
        self.resolver = resolver
        self.log = host_logging.get_logger(f"BotWorker:{bot.id}")

        self.driver_config = None
        self.driver = None

        self._current_job: Optional[Job] = bot.current_job
        self._thread = Thread(target=self._run, daemon=True)
        self._worker_should_be_stopped = Event()
        self._thread.start()

        self._last_progress_update = 0

    def stop(self):
        self._worker_should_be_stopped.set()
        self._thread.join(1)
        if self.driver is not None:
            self.driver.disconnect()

    def _handle_driver(self):
        # TODO Make this only disconnect and reconnect the driver when the bot is idle
        if self.bot.driver is not None:
            if self.driver_config == self.bot.driver:
                return
            else:
                self.driver_config = self.bot.driver

                if self.driver is not None:
                    self.driver.disconnect()

            self.driver = self.resolver(DriverFactory).get(self.driver_config)
            self.driver.connect()

    def _handle_job_available(self):
        if not self.bot.job_available:
            return

        BotEvents.BotHasJobAvailable(self.bot).fire()

    def _handle_job_assignment(self):
        if self.bot.current_job is None:
            return

        job = self.bot.current_job

        if job.status == 'assigned':
            JobEvents.JobAssigned(job, self.bot).fire()

    @on(BotEvents.BotUpdated)
    def _bot_updated(self, event: BotEvents.BotUpdated):
        if self.bot.id != event.bot.id:
            return

        if self.bot.status != 'idle' and event.bot.status == 'idle':
            get_a_job = self.resolver(GetAJob)
            get_a_job(self.bot.id)

        # TODO Handle offline bots
        self.bot = event.bot
        self._handle_driver()
        self._handle_job_available()
        self._handle_job_assignment()

    @on(BotEvents.BotHasJobAvailable)
    def _bot_has_job_available(self, event: BotEvents.BotHasJobAvailable):
        if self.bot.id != event.bot.id:
            return

        if self.bot.status != "idle":
            return

        get_a_job = self.resolver(GetAJob)
        get_a_job(self.bot.id)

    @on(JobEvents.JobAssigned)
    def job_assigned(self, event: JobEvents.JobAssigned):
        if self.bot.id != event.bot.id:
            return

        self._current_job = event.job

    def _update_job_progress(self, progress):
        if self._last_progress_update + 0.01 > progress:
            return

        try:
            update_job_progress = self.resolver(UpdateJobProgress)
            update_job_progress(self._current_job.id, progress)
        except ErrorResponse as e:
            if e.code == Errors.jobPercentageCanOnlyIncrease:
                self.log.info(f"Tried to set progress to {progress}, but the API says it's already higher")
            else:
                self.log.error("Unknown exception from API", exc_info=True)
        except Exception:
            self.log.error("Unknown other exception", exc_info=True)

    def _run(self):
        self.log.info(f"Bot started up with status: {self.bot.status}")
        if self.bot.status == "working":
            bot_error_command: BotError = self.resolver(BotError)
            bot_error_command(self.bot.id, 'Bot startup failure with job in working state')
            self.bot.status = "error"

            if self.bot.current_job is not None:
                self.bot.current_job.status = 'failed'

        self._handle_driver()
        self._handle_job_available()
        self._handle_job_assignment()

        while not self._worker_should_be_stopped.is_set():
            if self._current_job is not None and self._current_job.status == 'assigned':
                self.log.info(f"Starting on job {self._current_job.id}")
                url = self._current_job.file_url

                downloader = self.resolver(Downloader)
                self.log.info(f"Downloading {url}")
                filename = downloader.download(url)
                self.log.info(f"Downloaded {url} to {filename}")

                start_job_command = self.resolver(StartJob)
                start_job_command(self._current_job.id)

                self.log.info("Calling driver's run method")
                try:
                    self.driver.run(filename,
                                    update_job_progress=self._update_job_progress)
                except Exception:
                    self.log.error("Unknown exception from driver run method", exc_info=True)
                self.log.info("Driver's run method returned")

                finish_job_command = self.resolver(FinishJob)
                finish_job_command(self._current_job.id)

                self._current_job = None
            else:
                time.sleep(0.05)
