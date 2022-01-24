import uuid
from unittest.mock import MagicMock, Mock

from bqclient.host.api.commands.finish_job import FinishJob
from bqclient.host.api.commands.start_job import StartJob
from bqclient.host.downloader import Downloader
from bqclient.host.drivers.driver_factory import DriverFactory
from bqclient.host.drivers.dummy import DummyDriver
from bqclient.host.models import Bot, Job, File
from bqclient.host.workers.bot_worker import DriverUpdatedCommand, RunJobCommand
from tests.test_helpers import SideEffectEvent


class TestBotWorker(object):
    def test_empty_driver_does_not_connect_automatically(self, bot_worker_harness):
        bot: Bot = Mock(Bot)
        bot.driver = None
        with bot_worker_harness(bot) as _:
            pass

    def test_non_empty_driver_resolves_and_calls_connect(self, resolver, bot_worker_harness):
        driver_factory = MagicMock(DriverFactory)
        resolver.instance(driver_factory)

        dummy_driver = MagicMock(DummyDriver)
        driver_factory.get.return_value = dummy_driver

        bot: Bot = Mock(Bot)
        bot.driver = {"type": "dummy"}

        with bot_worker_harness(bot) as _:
            driver_factory.get.assert_called_once_with(bot.driver)
            dummy_driver.connect.assert_called_once()

    def test_driver_update_connects(self, resolver, bot_worker_harness):
        driver_factory = MagicMock(DriverFactory)
        resolver.instance(driver_factory)

        dummy_driver = MagicMock(DummyDriver)
        driver_factory.get.return_value = dummy_driver

        bot: Bot = Mock(Bot)
        bot.driver = None

        with bot_worker_harness(bot) as bwh:
            driver_factory.get.assert_not_called()
            dummy_driver.connect.assert_not_called()

            driver_config = {"type": "dummy"}

            bwh.send(DriverUpdatedCommand(driver_config))

            driver_factory.get.assert_called_once_with(driver_config)
            dummy_driver.connect.assert_called_once()

    def test_driver_update_disconnects_current_connection_before_reconnecting(self, resolver,
                                                                              bot_worker_harness):
        driver_factory = Mock(DriverFactory)
        resolver.instance(DriverFactory, driver_factory)

        dummy_driver = MagicMock(DummyDriver)
        driver_factory.get.return_value = dummy_driver

        driver_config = {"type": "dummy"}
        bot: Bot = Mock(Bot)
        bot.driver = driver_config

        with bot_worker_harness(bot) as bwh:
            driver_factory.get.assert_called_once_with(driver_config)
            dummy_driver.connect.assert_called_once()

            dummy_driver2 = MagicMock(DummyDriver)
            driver_factory.reset_mock()
            driver_factory.get.return_value = dummy_driver2

            bwh.send(DriverUpdatedCommand(driver_config))

            dummy_driver.disconnect.assert_called_once()
            driver_factory.get.assert_called_once_with(driver_config)
            dummy_driver2.connect.assert_called_once()

    def test_driver_update_disconnects_current_connection_but_does_not_reconnect_on_none_driver(self, resolver,
                                                                                                bot_worker_harness):
        driver_factory = Mock(DriverFactory)
        resolver.instance(DriverFactory, driver_factory)

        dummy_driver = MagicMock(DummyDriver)
        driver_factory.get.return_value = dummy_driver

        driver_config = {"type": "dummy"}
        bot: Bot = Mock(Bot)
        bot.driver = driver_config

        with bot_worker_harness(bot) as bwh:
            driver_factory.get.assert_called_once_with(driver_config)
            dummy_driver.connect.assert_called_once()

            driver_factory.reset_mock()

            bwh.send(DriverUpdatedCommand(None))

            dummy_driver.disconnect.assert_called_once()
            driver_factory.get.assert_not_called()

    def test_run_job_command_starts_job(self, resolver, bot_worker_harness):
        driver_factory = MagicMock(DriverFactory)
        resolver.instance(driver_factory)

        dummy_driver = MagicMock(DummyDriver)

        driver_start_event = SideEffectEvent()

        dummy_driver.start.side_effect = driver_start_event
        driver_factory.get.return_value = dummy_driver

        file: Mock = Mock(File)
        file.download_url = "http://example.com/foo.gcode"

        job: Mock = Mock(Job)
        job.id = uuid.uuid4()
        job.file = file

        driver_config = {"type": "dummy"}
        bot: Mock = Mock(Bot)
        bot.driver = driver_config
        bot.current_job = job

        downloader = MagicMock(Downloader)
        downloader.download.return_value = 'foo.gcode'
        resolver.instance(downloader)

        start_job = MagicMock(StartJob)
        start_job_event = SideEffectEvent()
        start_job.side_effect = start_job_event
        resolver.instance(start_job)

        finish_job = MagicMock(FinishJob)
        finish_job_event = SideEffectEvent()
        finish_job.side_effect = finish_job_event
        resolver.instance(finish_job)

        with bot_worker_harness(bot) as bwh:
            driver_factory.get.assert_called_once_with(driver_config)
            dummy_driver.connect.assert_called_once()

            bwh.send(RunJobCommand(job))

            start_job_event.wait()
            driver_start_event.wait()

            downloader.download.assert_called_once_with(file)

            start_job.assert_called_once_with(job.id)
            dummy_driver.start.assert_called_once_with('foo.gcode')

            finish_job.assert_not_called()

            dummy_driver.job_finished_callback()

            finish_job_event.wait()
            finish_job.assert_called_once_with(job.id)
