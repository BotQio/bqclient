from typing import Dict

from deepdiff import DeepDiff

from bqclient.host import on
from bqclient.host.api.commands.bot_error import BotError
from bqclient.host.api.commands.get_a_job import GetAJob
from bqclient.host.events import BotEvents
from bqclient.host.framework.events import bind_events
from bqclient.host.framework.ioc import Resolver, singleton
from bqclient.host.framework.logging import HostLogging
from bqclient.host.models import Bot
from bqclient.host.workers.bot_worker import BotWorker, ShutdownCommand, DriverUpdatedCommand, RunJobCommand

IDLE = "idle"
OFFLINE = "offline"
JOB_ASSIGNED = "job_assigned"
WORKING = "working"


@singleton
@bind_events
class WorkerManager(object):
    def __init__(self,
                 resolver: Resolver,
                 logging: HostLogging):
        self._resolver = resolver
        self._logger = logging.get_logger("WorkerManager")
        self._bots: Dict[str, Bot] = {}
        self._bot_workers: Dict[str, BotWorker] = {}

    @on(BotEvents.BotAdded)
    def _bot_added(self, event: BotEvents.BotAdded):
        bot: Bot = event.bot
        worker = self._resolver(BotWorker, bot)
        self._bot_workers[bot.id] = worker
        self._bots[bot.id] = bot

        if bot.status == WORKING:
            self._logger.info(f"Bot {bot.id} started up in working mode, setting to error state.")
            bot_error: BotError = self._resolver(BotError)
            bot_error(bot.id, "Bot startup in working mode.")

        elif bot.current_job_id is None and bot.job_available:
            get_a_job: GetAJob = self._resolver(GetAJob)
            get_a_job(bot.id)

        elif bot.status == JOB_ASSIGNED:
            worker.input_queue.put(RunJobCommand(bot.current_job))

    @on(BotEvents.BotRemoved)
    def _bot_removed(self, event: BotEvents.BotRemoved):
        bot: Bot = event.bot

        if bot.id not in self._bot_workers:
            return

        worker: BotWorker = self._bot_workers[bot.id]
        worker.input_queue.put(ShutdownCommand())
        del self._bot_workers[bot.id]
        del self._bots[bot.id]

    @on(BotEvents.BotUpdated)
    def _bot_updated(self, event: BotEvents.BotUpdated):
        current_bot: Bot = self._bots[event.bot.id]
        updated_bot: Bot = event.bot
        worker: BotWorker = self._bot_workers[event.bot.id]
        self._bots[event.bot.id] = updated_bot  # TODO Tests didn't catch the need for this

        driver_diff = DeepDiff(current_bot.driver, updated_bot.driver)
        if driver_diff:
            worker.input_queue.put(DriverUpdatedCommand(updated_bot.driver))

        call_get_a_job = self._should_get_a_job(current_bot, updated_bot)

        if call_get_a_job:
            self._logger.info("Calling to get a job")
            get_a_job: GetAJob = self._resolver(GetAJob)
            get_a_job(updated_bot.id)

        if updated_bot.status == JOB_ASSIGNED and current_bot.status != JOB_ASSIGNED:
            worker.input_queue.put(RunJobCommand(updated_bot.current_job))

    @staticmethod
    def _should_get_a_job(current_bot: Bot, updated_bot: Bot):
        if updated_bot.status == OFFLINE:
            return False

        if updated_bot.current_job_id is None and updated_bot.job_available:
            return True

        if current_bot.status != IDLE and updated_bot.status == IDLE:
            return True

        return False
