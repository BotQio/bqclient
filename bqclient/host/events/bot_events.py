from bqclient.host.framework.events import EventBag, Event
from bqclient.host.models import Bot


class BotEvents(EventBag):
    class BotAdded(Event):
        def __init__(self, bot: Bot):
            self.bot = bot

    class BotRemoved(Event):
        def __init__(self, bot: Bot):
            self.bot = bot

    class BotUpdated(Event):
        def __init__(self, bot: Bot):
            self.bot = bot

    class BotHasJobAvailable(Event):
        def __init__(self, bot: Bot):
            self.bot = bot
