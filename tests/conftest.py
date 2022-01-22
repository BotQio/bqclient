import os
import tempfile
import threading
import uuid
from typing import List, Dict, Any
from unittest.mock import MagicMock, Mock, PropertyMock

import pytest
import requests
from appdirs import AppDirs
from faker import Faker
from pysherplus.channel import EventCallback
from requests import Response

from bqclient.host.api.rest import RestApi
from bqclient.host.framework.events import Event, EventManager
from bqclient.host.framework.ioc import Resolver
from bqclient.host.api.channels.host_channel import HostSocketChannel as BaseHostChannel
from bqclient.host.models import Bot
from bqclient.host.workers.bot_worker import BotWorker, ShutdownCommand, WorkerCommand, NopCommand


@pytest.fixture
def resolver():
    Resolver.reset()
    resolver = Resolver.get()

    resolver.singleton(AppDirs, mock_appdirs)

    return resolver


def mock_appdirs():
    appdirs_mock = Mock(AppDirs)
    appdirs_mock.user_config_dir = os.path.join(tempfile.mkdtemp(), 'user_config_dir')
    appdirs_mock.user_log_dir = os.path.join(tempfile.mkdtemp(), 'user_log_dir')

    return appdirs_mock


@pytest.fixture
def user_config_dir(resolver):
    appdirs: AppDirs = resolver(AppDirs)
    return appdirs.user_config_dir


@pytest.fixture
def user_log_dir(resolver):
    appdirs: AppDirs = resolver(AppDirs)
    return appdirs.user_log_dir


@pytest.fixture
def dictionary_magic():
    def _dictionary_magic(mock):
        base = {}

        if hasattr(mock.__class__, '__getitem__'):
            mock.__getitem__.side_effect = base.__getitem__

        if hasattr(mock.__class__, '__contains__'):
            mock.__contains__.side_effect = base.__contains__

        if hasattr(mock.__class__, '__setitem__'):
            mock.__setitem__.side_effect = base.__setitem__

        if hasattr(mock.__class__, '__delitem__'):
            mock.__delitem__.side_effect = base.__delitem__

        return mock

    return _dictionary_magic


@pytest.fixture
def fakes_events(resolver):
    class EventAssertion(object):
        def __init__(self):
            self.events = []

        def __call__(self, event):
            self.events.append(event)

        def __bool__(self):
            return len(self.events) > 0

        def once(self):
            return self.times(1)

        def times(self, count):
            return len(self.events) == count

        @property
        def event(self):
            if not self.once():
                raise Exception("Cannot get the event if it was not emitted once")

            return self.events[0]

    class FakesEvents(object):
        def __init__(self):
            self._original: EventManager = resolver(EventManager)

            self._fire_function = lambda event: EventManager.fire(self._original, event)
            self._original.fire = MagicMock(side_effect=self._fire_function)

            self._event_assertions = {}

        def fake(self, event_class: type):
            if event_class not in self._event_assertions:
                self._event_assertions[event_class] = EventAssertion()

            def _internal(fired_event: Event):
                if isinstance(fired_event, event_class):
                    self._event_assertions[event_class](fired_event)
                else:
                    _internal.current_fire_function(fired_event)

            _internal.current_fire_function = self._fire_function

            self._fire_function = _internal
            self._original.fire.side_effect = self._fire_function

        def fired(self, event: Event) -> EventAssertion:
            return self._event_assertions[event]

    return FakesEvents()


@pytest.fixture
def mock_session(monkeypatch, dictionary_magic):
    class FakeSession(object):
        def __init__(self):
            self.headers = {}
            self.post = MagicMock()

    monkeypatch.setattr(requests, "Session", lambda: FakeSession())


@pytest.fixture
def fake_responses():
    class FakeResponses(object):
        @staticmethod
        def ok(return_value=None):
            response = MagicMock(Response)
            ok_mock = PropertyMock(return_value=True)
            type(response).ok = ok_mock
            if return_value is None:
                response.json.return_value = {}
            else:
                response.json.return_value = return_value

            return response

    return FakeResponses()


@pytest.fixture
def host_channel(resolver):
    # TODO Somehow make this not reimplement the entire API surface of HostSocketChannel
    class HostSocketChannel(object):
        def __init__(self):
            self._is_subscribed = False
            self._listeners: Dict[str, List[EventCallback]] = {}

        @property
        def subscribed(self) -> bool:
            return self._is_subscribed

        @subscribed.setter
        def subscribed(self, value: bool):
            self._is_subscribed = value

        def register(self, event_name: str, callback: EventCallback):
            self._listeners.setdefault(event_name, []).append(callback)

        def unregister(self, event_name: str, callback: EventCallback):
            listeners = self._listeners.setdefault(event_name, [])
            if callback in listeners:
                listeners.remove(callback)

        def event(self, event_name: str, data: Any):
            app_events_prefix = 'App\\Events\\'
            event_name_sans_prefix = event_name.removeprefix(app_events_prefix)

            # This allows subscribers to 'App\Events\Name' and 'Name'.
            # It will call the callback with their preferred format.
            for name in {event_name, event_name_sans_prefix}:
                if name not in self._listeners:
                    continue

                listener: EventCallback
                for listener in self._listeners[name]:
                    listener(name, data)

    channel = HostSocketChannel()
    resolver.instance(BaseHostChannel, channel)

    return channel


@pytest.fixture
def rest_api(resolver):
    rest_api = MagicMock(RestApi)
    resolver.instance(rest_api)

    return rest_api


@pytest.fixture
def bot_worker_harness(resolver):
    def _inner(bot: Bot):
        class BotWorkerHarness(object):
            def __init__(self, b: Bot):
                self._bot: Bot = b
                self._bot_worker: BotWorker = resolver(BotWorker, bot=self._bot)
                self._thread = threading.Thread(target=self._run, daemon=True)

            def send(self, command: WorkerCommand):
                self._bot_worker.input_queue.put(command)
                completed = command.completed.wait(0.5)

                if not completed:
                    raise ValueError(f"Command {command} not completed in time!")

            def _run(self):
                self._bot_worker.event_loop()

            def __enter__(self):
                self._thread.start()
                self.send(NopCommand())  # This helps avoid race conditions on assertions for the caller

                return self

            def __exit__(self, exc_type, exc_val, exc_tb):
                self.send(ShutdownCommand())
                self._thread.join(1)

                if self._thread.is_alive():
                    raise Exception("Bot Worker thread did not shutdown in time when asked.")

        return BotWorkerHarness(bot)

    return _inner
