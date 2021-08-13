from unittest.mock import Mock

from bqclient.host.api.botqio_api import BotQioApi
from bqclient.host.api.commands.get_a_job import GetAJob
from bqclient.host.events import JobEvents


class TestGetAJob(object):
    def test_get_job(self, resolver, fakes_events):
        fakes_events.fake(JobEvents.JobStarted)

        api = Mock(BotQioApi)
        resolver.instance(api)

        get_a_job = resolver(GetAJob)

        get_a_job(1)

        api.command.assert_called_with("GetAJob", {
            "bot": 1
        })
