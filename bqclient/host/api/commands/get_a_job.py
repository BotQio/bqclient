from bqclient.host.api.botqio_api import BotQioApi


class GetAJob(object):
    def __init__(self,
                 api: BotQioApi):
        self.api = api

    def __call__(self, bot_id):
        self.api.command("GetAJob", {
            "bot": bot_id
        })
