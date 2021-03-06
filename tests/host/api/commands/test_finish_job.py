from unittest.mock import Mock

from bqclient.host.api.botqio_api import BotQioApi
from bqclient.host.api.commands.finish_job import FinishJob
from bqclient.host.events import JobEvents


class TestFinishJob(object):
    def test_finishing_job(self, resolver, fakes_events):
        fakes_events.fake(JobEvents.JobFinished)

        api = Mock(BotQioApi)
        api.command.return_value = {
                "id": 1,
                "name": "My Job",
                "status": "in_progress",
                "url": "file_url"
            }
        resolver.instance(api)

        start_job = resolver(FinishJob)

        start_job(1)

        api.command.assert_called_once_with("FinishJob", {
            "id": 1
        })

        assert fakes_events.fired(JobEvents.JobFinished).once()

        event: JobEvents.JobFinished = fakes_events.fired(JobEvents.JobFinished).event
        assert event.job.id == 1
        assert event.job.name == "My Job"
        assert event.job.status == "in_progress"
        assert event.job.file_url == "file_url"
