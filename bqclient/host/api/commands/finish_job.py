from bqclient.host.api.botqio_api import BotQioApi
from bqclient.host.events import JobEvents
from bqclient.host.types import Job


class FinishJob(object):
    def __init__(self,
                 api: BotQioApi):
        self.api = api

    def __call__(self, job_id):
        response = self.api.command("FinishJob", {
            "id": job_id
        })
        
        job = Job(
            id=response["id"],
            name=response["name"],
            status=response["status"],
            file_url=response["url"]
        )

        JobEvents.JobFinished(job).fire()