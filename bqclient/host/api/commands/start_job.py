from bqclient.host.api.botqio_api import BotQioApi
from bqclient.host.events import JobEvents
from bqclient.host.models import Job


class StartJob(object):
    def __init__(self,
                 api: BotQioApi):
        self.api = api

    def __call__(self, job_id):
        response = self.api.command("StartJob", {
            "id": job_id
        })
        
        job = Job(self.api.rest, response)

        JobEvents.JobStarted(job).fire()