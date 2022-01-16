from typing import TypeVar, Generic, Iterator, Optional, Type
from urllib.parse import urljoin

import requests

from bqclient.host.api.server import Server
from bqclient.host.framework.ioc import singleton
from bqclient.host.models import Bot, Model, Job, File, User


class AccessTokenNotFound(Exception):
    pass


class RequestFailed(Exception):
    pass


class AccessDenied(RequestFailed):
    pass


class NotFound(RequestFailed):
    pass


T = TypeVar('T', bound=Model)


class Resource(Generic[T]):
    def __init__(self,
                 api: 'RestApi',
                 _type: Type[T],
                 url_list: Optional[str] = None,
                 url_fetch: Optional[str] = None):
        self._api = api
        self._type = _type
        self._url_list = url_list
        self._url_fetch = url_fetch

    def list(self) -> Iterator[T]:
        if self._url_list is None:
            raise ValueError("Cannot list with this resource")

        response = self._api.get(self._url_list)
        response_json = self._guard_bad_response(response)

        data = response_json['data']
        links = response_json['links']

        while data is not None:
            for element in data:
                yield Bot(self._api, element['data'])

            data = None
            next_link = links["next"] if "next" in links else None
            if next_link is not None:
                response_json = self._guard_bad_response(response)
                data = response_json['data']
                links = response_json['links']

    def fetch(self, _id: str) -> T:
        if self._url_fetch is None:
            raise ValueError("Cannot list with this resource")

        response = self._api.get(self._url_fetch.format(id=_id))
        response_json = self._guard_bad_response(response)

        return self._type(self._api, response_json['data'])

    @staticmethod
    def _guard_bad_response(response):
        if not response.ok:
            if response.status_code == 403:
                raise AccessDenied("You do not have access to that resource")

            if response.status_code == 404:
                raise NotFound("Could not find that resource")
            raise RequestFailed(f"Response status code was {response.status_code}: {response.content}")
        response_json = response.json()
        if not response_json['ok']:
            raise RequestFailed(f"Data was not ok: {response_json}")

        return response_json


# @singleton
class RestApi(object):
    def __init__(self,
                 server: Server):
        self._server = server
        self.session = requests.Session()
        self.session.headers.update({
            "Content-Type": "application/json",
            "Accept": "application/json"
        })

        self._bots: Optional[Resource[Bot]] = None
        self._jobs: Optional[Resource[Job]] = None
        self._files: Optional[Resource[File]] = None
        self._users: Optional[Resource[User]] = None

    @property
    def bots(self) -> Resource[Bot]:
        if self._bots is None:
            self._bots = Resource(
                api=self,
                _type=Bot,
                url_list='/api/bots',
                url_fetch='/api/bots/{id}'
            )

        return self._bots

    @property
    def jobs(self) -> Resource[Job]:
        if self._jobs is None:
            self._jobs = Resource(
                api=self,
                _type=Job,
                url_list='/api/jobs',
                url_fetch='/api/jobs/{id}'
            )

        return self._jobs

    @property
    def files(self) -> Resource[File]:
        if self._files is None:
            self._files = Resource(
                api=self,
                _type=File,
                url_fetch='/api/files/{id}'
            )

        return self._files

    @property
    def users(self) -> Resource[User]:
        if self._users is None:
            self._users = Resource(
                api=self,
                _type=User,
                url_fetch='/api/users/{id}'
            )

        return self._users

    def _ensure_bearer_token(self):
        if self._server.access_token is not None:
            access_token = self._server.access_token

            self.session.headers.update({"Authorization": f"Bearer {access_token}"})

    def get(self, url, params=None):
        self._ensure_bearer_token()

        params = params if params is not None else {}

        full_url = urljoin(self._server.url, url) if not url.startswith(self._server.url) else url
        return self.session.get(full_url, params=params)

    def post(self, url, data=None):
        self._ensure_bearer_token()

        json = data if data is not None else {}

        full_url = urljoin(self._server.url, url) if not url.startswith(self._server.url) else url
        return self.session.post(full_url, json=json)
