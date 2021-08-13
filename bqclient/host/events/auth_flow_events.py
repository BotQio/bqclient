from bqclient.host.framework.events import EventBag, Event
from bqclient.host.types import HostRequest, Host


class AuthFlowEvents(EventBag):
    class HostRequestMade(Event):
        def __init__(self, host_request: HostRequest):
            self.host_request = host_request

    class HostMade(Event):
        def __init__(self, host: Host):
            self.host = host
