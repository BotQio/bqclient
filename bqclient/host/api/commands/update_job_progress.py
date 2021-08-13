from bqclient.host.api.botqio_api import BotQioApi


class UpdateJobProgress(object):
    def __init__(self,
                 api: BotQioApi):
        self.api = api

    def __call__(self, job_id, percentage):
        self.api.command("UpdateJobProgress", {
            "id": job_id,
            "progress": percentage
        })
