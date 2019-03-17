from urllib.parse import urljoin

import requests

from bumblebee.host.configurations import HostConfiguration


class AccessTokenNotFound(Exception):
    pass


class RestApi(object):
    def __init__(self,
                 config: HostConfiguration):
        self._headers = {
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        self.config = config

    def post(self, url, data=None):
        json = data if data is not None else {}

        if "access_token" in self.config:
            access_token = self.config["access_token"]

            self._headers["Authorization"] = f"Bearer {access_token}"

        full_url = urljoin(self.config["server"], url)
        return requests.post(full_url, json=json, headers=self._headers)
