from typing import List, Any

from deepdiff import DeepDiff

from bqclient.host.api.botqio_api import BotQioApi
from bqclient.host.api.channels.host_channel import HostSocketChannel
from bqclient.host.api.rest import RestApi
from bqclient.host.events import BotEvents
from bqclient.host.framework.recurring_task import RecurringTask
from bqclient.host.models import Bot


class BotsManager(object):
    def __init__(self,
                 api: BotQioApi,
                 rest_api: RestApi,
                 host_channel: HostSocketChannel):
        self.api = api
        self._rest_api = rest_api
        self._host_channel = host_channel

        self._bots = {}
        self._polling_thread = RecurringTask(60, self.poll)

        self._host_channel.register('BotUpdated', self._socket_bot_updated)
        self._host_channel.register('JobAssignedToBot', self._socket_bot_updated)

    def start(self):
        self._polling_thread.start()

    def poll(self):
        if self._host_channel.subscribed:
            return

        response = self.api.command("GetBots")

        _bot_ids_seen_in_response = []
        for bot_json in response:
            bot = Bot(self._rest_api, bot_json)

            if bot.id not in self._bots:
                BotEvents.BotAdded(bot).fire()
            else:
                diff = DeepDiff(self._bots[bot.id], bot)
                if diff:
                    BotEvents.BotUpdated(bot).fire()

            _bot_ids_seen_in_response.append(bot.id)
            self._bots[bot.id] = bot

        for bot_id in list(self._bots.keys()):
            if bot_id not in _bot_ids_seen_in_response:
                BotEvents.BotRemoved(self._bots[bot_id]).fire()
                del self._bots[bot_id]

    def _socket_bot_updated(self, _: str, data: Any):
        bot = Bot(self._rest_api, data["bot"])

        if bot.id not in self._bots:
            BotEvents.BotAdded(bot).fire()
        else:
            diff = DeepDiff(self._bots[bot.id], bot)
            if diff:
                BotEvents.BotUpdated(bot).fire()

        self._bots[bot.id] = bot
