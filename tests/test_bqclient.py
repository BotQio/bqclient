from unittest.mock import MagicMock

import pytest

from bumblebee.bot_worker import BotWorker
from bumblebee.bqclient import BQClient
from bumblebee.host.events import BotEvents
from bumblebee.host.types import Bot, User


class TestBQClient(object):
    def test_bot_worker_is_created_when_bot_is_added(self, resolver):
        call_count = 0

        def get_bot_worker(bot_id):
            if bot_id != 1:
                pytest.fail("Resolving function did not request the correct bot id")

            nonlocal call_count
            call_count = call_count + 1

            mock = MagicMock(BotWorker)
            return mock

        resolver.bind(BotWorker, get_bot_worker)

        # Make sure the client binds its events
        resolver(BQClient)

        bot = Bot(
            id=1,
            name="Test Bot",
            status="Idle",
            type="3d_printer"
        )

        BotEvents.BotAdded(bot).fire()

        assert call_count == 1
