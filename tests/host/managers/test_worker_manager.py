import uuid
from queue import Queue
from unittest.mock import Mock, MagicMock

from bqclient.host.api.commands.bot_error import BotError
from bqclient.host.api.commands.get_a_job import GetAJob
from bqclient.host.events import BotEvents
from bqclient.host.managers.worker_manager import WorkerManager
from bqclient.host.models import Bot, Job
from bqclient.host.workers.bot_worker import BotWorker, ShutdownCommand, DriverUpdatedCommand, RunJobCommand


class TestWorkerManager(object):
    def test_bot_added_creates_worker(self, resolver):
        bot: Bot = Mock(Bot)
        bot.job_available = False
        bot.status = "idle"
        worker: BotWorker = Mock()

        bot_asserted = False

        def _internal(test_bot: Bot):
            nonlocal bot_asserted
            bot_asserted = True

            assert test_bot is bot

            return worker

        resolver.bind(BotWorker, _internal)

        _ = resolver(WorkerManager)

        BotEvents.BotAdded(bot).fire()

        assert bot_asserted

    def test_bot_removed_shuts_down_worker(self, resolver):
        bot: Bot = Mock(Bot)
        bot.job_available = False
        bot.status = "idle"
        worker: BotWorker = Mock(BotWorker)
        queue: MagicMock = MagicMock(Queue)

        worker.input_queue = queue
        resolver.instance(BotWorker, worker)

        _ = resolver(WorkerManager)

        BotEvents.BotAdded(bot).fire()

        queue.put.assert_not_called()

        BotEvents.BotRemoved(bot).fire()

        queue.put.assert_called_once()
        assert isinstance(queue.put.call_args[0][0], ShutdownCommand)

    def test_bot_updated_with_driver_sends_driver_update(self, resolver):
        bot: Bot = MagicMock(Bot)
        bot.id = uuid.uuid4()
        bot.driver = {"type": "dummy"}
        bot.job_available = False
        bot.status = "idle"
        worker: BotWorker = Mock(BotWorker)
        queue: MagicMock = MagicMock(Queue)

        worker.input_queue = queue
        resolver.instance(BotWorker, worker)

        _ = resolver(WorkerManager)

        BotEvents.BotAdded(bot).fire()

        queue.put.assert_not_called()

        updated_bot: Bot = MagicMock(Bot)
        updated_bot.id = bot.id

        updated_config = {"type": "gcode"}
        updated_bot.driver = updated_config
        updated_bot.job_available = False
        updated_bot.status = "idle"

        BotEvents.BotUpdated(updated_bot).fire()

        queue.put.assert_called_once()
        arg = queue.put.call_args[0][0]
        assert isinstance(arg, DriverUpdatedCommand)
        assert arg.driver_config == updated_config

    def test_bot_updated_with_driver_sends_driver_update_from_none(self, resolver):
        bot: Bot = MagicMock(Bot)
        bot.id = uuid.uuid4()
        bot.driver = None
        bot.job_available = False
        bot.status = "idle"
        worker: BotWorker = Mock(BotWorker)
        queue: MagicMock = MagicMock(Queue)

        worker.input_queue = queue
        resolver.instance(BotWorker, worker)

        _ = resolver(WorkerManager)

        BotEvents.BotAdded(bot).fire()

        queue.put.assert_not_called()

        updated_bot: Bot = MagicMock(Bot)
        updated_bot.id = bot.id

        updated_config = {"type": "gcode"}
        updated_bot.driver = updated_config
        updated_bot.job_available = False
        updated_bot.status = "idle"

        BotEvents.BotUpdated(updated_bot).fire()

        queue.put.assert_called_once()
        arg = queue.put.call_args[0][0]
        assert isinstance(arg, DriverUpdatedCommand)
        assert arg.driver_config == updated_config

    def test_bot_updated_with_driver_sends_driver_update_to_none(self, resolver):
        bot: Bot = MagicMock(Bot)
        bot.id = uuid.uuid4()
        bot.driver = {"type": "dummy"}
        bot.job_available = False
        bot.status = "idle"
        worker: BotWorker = Mock(BotWorker)
        queue: MagicMock = MagicMock(Queue)

        worker.input_queue = queue
        resolver.instance(BotWorker, worker)

        _ = resolver(WorkerManager)

        BotEvents.BotAdded(bot).fire()

        queue.put.assert_not_called()

        updated_bot: Bot = MagicMock(Bot)
        updated_bot.id = bot.id

        updated_config = None
        updated_bot.driver = updated_config
        updated_bot.job_available = False
        updated_bot.status = "idle"

        BotEvents.BotUpdated(updated_bot).fire()

        queue.put.assert_called_once()
        arg = queue.put.call_args[0][0]
        assert isinstance(arg, DriverUpdatedCommand)
        assert arg.driver_config == updated_config

    def test_bot_added_with_job_available_calls_get_a_job(self, resolver):
        bot: Bot = MagicMock(Bot)
        bot.id = uuid.uuid4()
        bot.job_available = True
        bot.status = "idle"
        bot.current_job_id = None
        worker: BotWorker = Mock(BotWorker)

        resolver.instance(BotWorker, worker)

        get_a_job = MagicMock(GetAJob)
        resolver.instance(get_a_job)

        _ = resolver(WorkerManager)

        BotEvents.BotAdded(bot).fire()

        get_a_job.assert_called_once_with(bot.id)

    def test_bot_updated_with_job_available_calls_get_a_job(self, resolver):
        bot: Bot = MagicMock(Bot)
        bot.id = uuid.uuid4()
        bot.job_available = False
        bot.status = "idle"
        bot.current_job_id = None
        worker: BotWorker = Mock(BotWorker)

        resolver.instance(BotWorker, worker)

        get_a_job = MagicMock(GetAJob)
        resolver.instance(get_a_job)

        _ = resolver(WorkerManager)

        BotEvents.BotAdded(bot).fire()

        get_a_job.assert_not_called()

        bot.job_available = True
        BotEvents.BotUpdated(bot).fire()

        get_a_job.assert_called_once_with(bot.id)

    def test_offline_bot_added_with_job_available_does_not_call_get_a_job(self, resolver):
        bot: Bot = MagicMock(Bot)
        bot.id = uuid.uuid4()
        bot.job_available = True
        bot.status = "offline"
        worker: BotWorker = Mock(BotWorker)

        resolver.instance(BotWorker, worker)

        get_a_job = MagicMock(GetAJob)
        resolver.instance(get_a_job)

        _ = resolver(WorkerManager)

        BotEvents.BotAdded(bot).fire()

        get_a_job.assert_not_called()

    def test_offline_bot_updated_with_job_available_does_not_call_get_a_job(self, resolver):
        bot: Bot = MagicMock(Bot)
        bot.id = uuid.uuid4()
        bot.job_available = False
        bot.current_job_id = None
        bot.status = "idle"
        worker: BotWorker = Mock(BotWorker)
        queue: MagicMock = MagicMock(Queue)

        worker.input_queue = queue
        resolver.instance(BotWorker, worker)

        get_a_job = MagicMock(GetAJob)
        resolver.instance(get_a_job)

        _ = resolver(WorkerManager)

        BotEvents.BotAdded(bot).fire()

        get_a_job.assert_not_called()

        updated_bot: Bot = MagicMock(Bot)
        updated_bot.id = bot.id

        updated_bot.driver = None
        updated_bot.job_available = True
        updated_bot.current_job_id = None
        updated_bot.status = "offline"
        BotEvents.BotUpdated(updated_bot).fire()

        get_a_job.assert_not_called()

    def test_bot_added_with_current_job_id_and_job_available_does_not_call_get_a_job(self, resolver):
        bot: Bot = MagicMock(Bot)
        bot.id = uuid.uuid4()
        bot.job_available = True
        bot.status = "waiting"
        bot.current_job_id = uuid.uuid4()
        worker: BotWorker = Mock(BotWorker)

        resolver.instance(BotWorker, worker)

        get_a_job = MagicMock(GetAJob)
        resolver.instance(get_a_job)

        _ = resolver(WorkerManager)

        BotEvents.BotAdded(bot).fire()

        get_a_job.assert_not_called()

    def test_bot_updated_with_current_job_id_and_job_available_does_not_call_get_a_job(self, resolver):
        bot: Bot = MagicMock(Bot)
        bot.id = uuid.uuid4()
        bot.job_available = False
        bot.status = "waiting"
        bot.current_job_id = uuid.uuid4()
        worker: BotWorker = Mock(BotWorker)

        resolver.instance(BotWorker, worker)

        get_a_job = MagicMock(GetAJob)
        resolver.instance(get_a_job)

        _ = resolver(WorkerManager)

        BotEvents.BotAdded(bot).fire()

        get_a_job.assert_not_called()

        bot.job_available = True
        BotEvents.BotUpdated(bot).fire()

        get_a_job.assert_not_called()

    def test_bot_added_with_assigned_job_runs_job(self, resolver):
        job: Job = Mock(Job)
        job.id = uuid.uuid4()

        bot: Bot = MagicMock(Bot)
        bot.id = uuid.uuid4()
        bot.job_available = False
        bot.status = "job_assigned"
        bot.current_job_id = job.id
        bot.current_job = job

        worker: BotWorker = Mock(BotWorker)
        queue: MagicMock = MagicMock(Queue)

        worker.input_queue = queue
        resolver.instance(BotWorker, worker)

        _ = resolver(WorkerManager)

        queue.put.assert_not_called()

        BotEvents.BotAdded(bot).fire()

        queue.put.assert_called_once()
        args = queue.put.call_args[0][0]
        assert isinstance(args, RunJobCommand)
        assert args.job is job

    def test_bot_updated_with_assigned_job_runs_job(self, resolver):
        bot: Bot = MagicMock(Bot)
        bot.id = uuid.uuid4()
        bot.driver = None
        bot.job_available = True
        bot.status = "idle"
        bot.current_job_id = None
        worker: BotWorker = Mock(BotWorker)
        queue: MagicMock = MagicMock(Queue)

        worker.input_queue = queue
        resolver.instance(BotWorker, worker)

        get_a_job = MagicMock(GetAJob)
        resolver.instance(get_a_job)

        _ = resolver(WorkerManager)

        BotEvents.BotAdded(bot).fire()

        get_a_job.assert_called_once_with(bot.id)

        updated_bot: Bot = MagicMock(Bot)
        updated_bot.id = bot.id

        job: Job = Mock(Job)
        job.id = uuid.uuid4()
        updated_bot.driver = None
        updated_bot.job_available = False
        updated_bot.status = "job_assigned"
        updated_bot.current_job_id = job.id
        updated_bot.current_job = job

        BotEvents.BotUpdated(updated_bot).fire()

        queue.put.assert_called_once()
        args = queue.put.call_args[0][0]
        assert isinstance(args, RunJobCommand)
        assert args.job is job

    def test_bot_going_to_idle_calls_get_a_job_regardless_of_job_available(self, resolver):
        bot: Bot = MagicMock(Bot)
        bot.id = uuid.uuid4()
        bot.job_available = False
        bot.status = "offline"
        worker: BotWorker = Mock(BotWorker)
        queue: MagicMock = MagicMock(Queue)

        worker.input_queue = queue
        resolver.instance(BotWorker, worker)

        get_a_job = MagicMock(GetAJob)
        resolver.instance(get_a_job)

        _ = resolver(WorkerManager)

        BotEvents.BotAdded(bot).fire()

        get_a_job.assert_not_called()

        updated_bot: Bot = MagicMock(Bot)
        updated_bot.id = bot.id
        updated_bot.driver = None
        updated_bot.job_available = False
        updated_bot.status = "idle"
        BotEvents.BotUpdated(updated_bot).fire()

        get_a_job.assert_called_once_with(bot.id)

    def test_bot_added_in_working_state_throws_error(self, resolver):
        bot: Bot = MagicMock(Bot)
        bot.id = uuid.uuid4()
        bot.job_available = False
        bot.status = "working"
        worker: BotWorker = Mock(BotWorker)

        resolver.instance(BotWorker, worker)

        bot_error = MagicMock(BotError)
        resolver.instance(bot_error)

        _ = resolver(WorkerManager)

        BotEvents.BotAdded(bot).fire()

        bot_error.assert_called_once()
        args = bot_error.call_args[0]
        assert args[0] == bot.id
        assert args[1] == 'Bot startup in working mode.'
