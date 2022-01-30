class HostRequest(object):
    def __init__(self,
                 id: int,
                 status: str,
                 server: str):
        self.id = id
        self.status = status
        self.server = server

    @property
    def url(self):
        return f"{self.server}/hosts/requests/{self.id}"


class Host(object):
    def __init__(self,
                 id: int,
                 name: str):
        self.id = id
        self.name = name
