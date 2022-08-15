import abc
import json
from datetime import datetime
from typing import TYPE_CHECKING, TypeVar, Generic, Optional, Dict, Any, Union

if TYPE_CHECKING:
    from bqclient.host.api.rest import RestApi


class DataCarrier(object):
    def __init__(self, data):
        self.data = data
        self.updated = {}

    def updated_or_data(self, name: str):
        return self.updated[name] if name in self.updated else self.data[name]

    def __eq__(self, other: 'DataCarrier'):
        updated_us = {**self.data, **self.updated}
        updated_other = {**other.data, **other.updated}

        return updated_us == updated_other


T = TypeVar('T')
U = TypeVar('U')


class Transform(Generic[T, U]):
    @abc.abstractmethod
    def from_stated(self, value: T) -> U:
        pass

    @abc.abstractmethod
    def to_stated(self, value: U) -> T:
        pass


class ReadOnlyValue(Generic[T]):
    def __init__(self,
                 name: str,
                 transform: Optional[Transform[T, U]] = None
                 ):
        self._name = name
        self._transform: Optional[Transform[T, U]] = transform
        self._transformed_value: Dict[int, U] = {}

    def __get__(self, instance, owner):
        # getattr just to avoid the protected member warning
        data: DataCarrier = getattr(instance, '_data')
        value = data.updated_or_data(self._name)

        if self._transform is not None:
            instance_id = id(instance)
            if instance_id not in self._transformed_value:
                self._transformed_value[instance_id] = self._transform.to_stated(value)
            value = self._transformed_value[instance_id]

        return value

    def __set__(self, instance, value):
        raise AttributeError(f"Attribute \"{self._name}\" is read only")


class Value(ReadOnlyValue[T]):
    def __init__(self,
                 name: str,
                 transform: Optional[Transform[T, U]] = None):
        super().__init__(name, transform)

    def __set__(self, instance, value):
        # getattr just to avoid the protected member warning
        data: DataCarrier = getattr(instance, '_data')
        data.updated[self._name] = value
        del self._transformed_value[id(instance)]


class Model(object):
    def __init__(self, api: 'RestApi', data):
        self._api = api
        self._data = DataCarrier(data)

    id: ReadOnlyValue[str] = ReadOnlyValue('id')

    def refresh(self):
        self._data = self._api.bots.fetch(self.id)._data

    def __eq__(self, other: Union['Model', DataCarrier, Dict]):
        if isinstance(other, Model):
            other = other._data
        elif isinstance(other, DataCarrier):
            pass  # Compare directly below
        elif isinstance(other, Dict):
            other = DataCarrier(other)

        return self._data == other


class DateTimeTransform(Transform[datetime, str]):
    def from_stated(self, value: datetime) -> str:
        result = value.isoformat()
        if result.endswith("00:00"):
            result = result[:-6] + 'Z'

        return result

    def to_stated(self, value: str) -> datetime:
        if value.endswith('Z'):
            value = value[:-1] + '+00:00'

        return datetime.fromisoformat(value)


class JsonTransform(Transform[Dict[str, Any], str]):
    def from_stated(self, value: Optional[Dict[str, Any]]) -> Optional[str]:
        if value is None:
            return None
        return json.dumps(value)

    def to_stated(self, value: str) -> Optional[Dict[str, Any]]:
        if value is None:
            return None
        return json.loads(value)


class Bot(Model):
    creator_id: ReadOnlyValue[str] = ReadOnlyValue('creator_id')
    host_id: Value[str] = Value('host_id')
    cluster_id: Value[str] = Value('cluster_id')
    current_job_id: ReadOnlyValue[str] = ReadOnlyValue('current_job_id')

    name: Value[str] = Value('name')
    type: ReadOnlyValue[str] = ReadOnlyValue('type')
    status: Value[str] = Value('status')
    error_text: Value[str] = Value('error_text')
    driver: Value[str] = Value('driver', transform=JsonTransform())
    job_available: ReadOnlyValue[bool] = ReadOnlyValue('job_available')

    # seen_at: ReadOnlyValue[str] = ReadOnlyValue('seen_at')  # TODO Does this go here on the API side?
    created_at: ReadOnlyValue[datetime] = ReadOnlyValue('created_at', transform=DateTimeTransform())
    updated_at: ReadOnlyValue[datetime] = ReadOnlyValue('updated_at', transform=DateTimeTransform())

    @property
    def current_job(self) -> Optional['Job']:
        if self.current_job_id is None:
            return None

        return self._api.jobs.fetch(self.current_job_id)

    @property
    def creator(self) -> 'User':
        return self._api.users.fetch(self.creator_id)


class Job(Model):
    creator_id: ReadOnlyValue[str] = ReadOnlyValue('creator_id')
    worker_id: ReadOnlyValue[str] = ReadOnlyValue('worker_id')
    worker_type: ReadOnlyValue[str] = ReadOnlyValue('worker_type')
    bot_id: ReadOnlyValue[Optional[str]] = ReadOnlyValue('bot_id')
    file_id: ReadOnlyValue[str] = ReadOnlyValue('file_id')

    name: Value[str] = Value('name')
    status: Value[str] = Value('status')
    progress: Value[str] = Value('progress')

    created_at: ReadOnlyValue[datetime] = ReadOnlyValue('created_at', transform=DateTimeTransform())
    updated_at: ReadOnlyValue[datetime] = ReadOnlyValue('updated_at', transform=DateTimeTransform())

    @property
    def file(self) -> 'File':
        return self._api.files.fetch(self.file_id)

    @property
    def creator(self) -> 'User':
        return self._api.users.fetch(self.creator_id)


class File(Model):
    uploader_id: ReadOnlyValue[str] = ReadOnlyValue('uploader_id')

    name: Value[str] = Value('name')
    size: ReadOnlyValue[int] = ReadOnlyValue('size')
    type: ReadOnlyValue[str] = ReadOnlyValue('type')
    download_url: ReadOnlyValue[str] = ReadOnlyValue('download_url')

    created_at: ReadOnlyValue[datetime] = ReadOnlyValue('created_at', transform=DateTimeTransform())
    updated_at: ReadOnlyValue[datetime] = ReadOnlyValue('updated_at', transform=DateTimeTransform())

    @property
    def creator(self) -> 'User':
        return self._api.users.fetch(self.uploader_id)


class User(Model):
    username: ReadOnlyValue['str'] = ReadOnlyValue('username')

    created_at: ReadOnlyValue[datetime] = ReadOnlyValue('created_at', transform=DateTimeTransform())
    updated_at: ReadOnlyValue[datetime] = ReadOnlyValue('updated_at', transform=DateTimeTransform())
