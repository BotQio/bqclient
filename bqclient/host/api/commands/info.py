from bqclient.host.api.botqio_api import BotQioApi


class Info(object):
    def __init__(self,
                 api: BotQioApi):
        self._api = api

    def __call__(self):
        return self._api.command('Info')
